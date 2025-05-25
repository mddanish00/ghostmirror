#include <notstd/core.h>
#include <notstd/str.h>

#include <gm/archive.h>

#include <archive.h>
#include <zlib.h>
#include <zstd.h>

void* gzip_decompress(void* data) {
	z_stream strm;
	memset(&strm, 0, sizeof(strm));
	if( inflateInit2(&strm, 16 + MAX_WBITS) != Z_OK ) die("Unable to initialize zlib");
	size_t datasize = mem_header(data)->len;
	size_t framesize = datasize * 2; // Initial estimate
	void* dec = MANY(char, framesize);
	mem_header(dec)->len = 0; // Initialize current decompressed size
	
	strm.avail_in  = datasize;
	strm.next_in   = (Bytef*)data;
	
	int ret;
	do{
		// Prepare output buffer for this iteration
		strm.avail_out = mem_available(dec);
		strm.next_out  = (Bytef*)mem_addressing(dec, mem_header(dec)->len);

		ret = inflate(&strm, Z_NO_FLUSH);
		
		// Update how much was decompressed in this iteration
		size_t decompressed_this_iteration = mem_available(dec) - strm.avail_out;
		mem_header(dec)->len += decompressed_this_iteration;

		if( ret != Z_OK && ret != Z_STREAM_END ){
			switch( ret ){
				case Z_DATA_ERROR:
					errno = EBADMSG;
				break;
				default:
					errno = EINVAL; // Generic error
				break;
			}
			mem_free(dec);
			dbg_error("gzip decompression failed %d: %s", ret, zError(ret));
			return NULL;
		}
		
		if (strm.avail_out == 0 && ret != Z_STREAM_END) { // Output buffer full, need to resize
			// Double the current capacity, or add a significant chunk
			size_t current_capacity = mem_header(dec)->len + mem_available(dec);
			size_t new_capacity = current_capacity * 2; 
			// Ensure new_capacity is larger, especially if current_capacity was 0 (though MANY should prevent this)
			if (new_capacity <= current_capacity) new_capacity = current_capacity + framesize;


			dec = mem_upsize(dec, new_capacity - current_capacity); // mem_upsize adds to current_capacity
			// framesize here is just a chunk size hint for upsize, could be ZSTD_DStreamOutSize() too
		}
	}while( ret != Z_STREAM_END );
	
	inflateEnd(&strm);
	return dec;
}

void* zstd_decompress(void* data) {
	ZSTD_DStream* dstream = ZSTD_createDStream();
	if (!dstream) {
		errno = ENOMEM; // Or some other appropriate error
		dbg_error("Failed to create ZSTD_DStream");
		return NULL;
	}

	size_t init_ret = ZSTD_initDStream(dstream);
	if (ZSTD_isError(init_ret)) {
		ZSTD_freeDStream(dstream);
		errno = EINVAL; // Or map ZSTD error code
		dbg_error("ZSTD_initDStream error: %s", ZSTD_getErrorName(init_ret));
		return NULL;
	}

	size_t datasize = mem_header(data)->len;
	ZSTD_inBuffer input = { data, datasize, 0 };

	// Initial output buffer size
	// Using ZSTD_DStreamOutSize() as recommended for streaming.
	size_t out_buffer_size = ZSTD_DStreamOutSize();
	void* dec = MANY(char, out_buffer_size);
	if (!dec) { // Should not happen if MANY dies on error, but good practice
		ZSTD_freeDStream(dstream);
		errno = ENOMEM;
		dbg_error("Failed to allocate initial memory for ZSTD decompression");
		return NULL;
	}
	mem_header(dec)->len = 0; // No data decompressed yet

	size_t zstd_ret;
	do {
		ZSTD_outBuffer output = { mem_addressing(dec, mem_header(dec)->len), mem_available(dec), 0 };

		zstd_ret = ZSTD_decompressStream(dstream, &output, &input);

		if (ZSTD_isError(zstd_ret)) {
			ZSTD_freeDStream(dstream);
			mem_free(dec);
			// Map ZSTD error codes to errno more specifically if possible
			if (ZSTD_getErrorCode(zstd_ret) == ZSTD_error_prefix_unknown) {
				errno = EBADMSG; // Data error seems appropriate
			} else {
				errno = EINVAL; // Generic error for other ZSTD issues
			}
			dbg_error("ZSTD_decompressStream error: %s", ZSTD_getErrorName(zstd_ret));
			return NULL;
		}

		mem_header(dec)->len += output.pos;

		// If output buffer is full and ZSTD_decompressStream hints there might be more data (ret > 0),
		// or if not all input is consumed yet.
		if (output.pos == output.size && (zstd_ret > 0 || input.pos < input.size)) {
			// Upsize the buffer. Add another ZSTD_DStreamOutSize() chunk.
			// mem_upsize expects the additional size, not the new total size.
			dec = mem_upsize(dec, ZSTD_DStreamOutSize()); 
			if (!dec) { // Should not happen if mem_upsize dies on error
				ZSTD_freeDStream(dstream);
				// Original dec was freed by mem_upsize on failure, if it works that way,
				// otherwise, we might need to free it here. Assuming mem_upsize handles it.
				errno = ENOMEM;
				dbg_error("Failed to upsize memory for ZSTD decompression");
				return NULL; // Critical error
			}
		}
	} while (zstd_ret > 0 || input.pos < input.size); 
	// Loop continues if ZSTD_decompressStream returns > 0 (meaning more frames to decompress or data to flush)
	// or if there's still input data that hasn't been processed.
	// Loop terminates when ZSTD_decompressStream returns 0 (all input consumed and flushed).

	ZSTD_freeDStream(dstream);
	return dec;
}

#define TAR_BLK  148
#define TAR_CHK  8
#define TAR_SIZE 512
#define TAR_MAGIC "ustar"

typedef struct htar_s{
	char name[100];
	char mode[8];
	char uid[8];
	char gid[8];
	char size[12];
	char mtime[12];
	char checksum[8];
	char typeflag;
	char linkname[100];
	char magic[6];
	char version[2];
	char uname[32];
	char gname[32];
	char devmajor[8];
	char devminor[8];
	char prefix[155];
	char pad[12];
}htar_s;

__private htar_s zerotar;

void tar_mopen(tar_s* tar, void* data){
	tar->start  = data;
	tar->loaddr = (uintptr_t)data;
	tar->end    = tar->loaddr + mem_header(data)->len;
	tar->err    = 0;
	//dbg_info("start: %lu end: %lu tot: %lu n: %lu", tar->loaddr, tar->end, tar->end-tar->loaddr, (tar->end-tar->loaddr)/512);
	memset(&tar->global, 0, sizeof tar->global);
}

__private unsigned tar_checksum(void* data){
	uint8_t* d = (uint8_t*) data;
	unsigned i;
	unsigned chk = 0;
	
	for( i = 0; i < TAR_BLK; ++i )
		chk += d[i];
	for( unsigned k = 0; k < TAR_CHK; ++k )
		chk += ' ';
	i += TAR_CHK;
	for( ; i < sizeof(htar_s); ++i )
		chk += d[i];
	
	return chk;
}

__private htar_s* htar_get(tar_s* tar){
	if( tar->loaddr >= tar->end ){
		dbg_error("out of tar bound");
		tar->err = ENOENT;
		return NULL;
	}
	htar_s* h = (htar_s*)tar->loaddr;
	if( !memcmp(h, &zerotar, sizeof zerotar) ){
		tar->loaddr += sizeof(htar_s);
		if( tar->loaddr >= tar->end ){
			dbg_error("no more data");
			tar->err = ENOENT;
			return NULL;
		}
		h = (htar_s*)tar->loaddr;
		if( !memcmp(h, &zerotar, sizeof zerotar) ){
			//dbg_info("end of tar");
			return NULL;
		}
		dbg_error("aspected end block");
		tar->err = EBADF;
		return NULL;
	}
	
	unsigned chk = strtoul(h->checksum, NULL, 8);
	if( chk != tar_checksum(h) ){
		dbg_error("wrong checksum");
		tar->err = EBADE;
		return NULL;
	}
	if( strcmp(h->magic, TAR_MAGIC) ){
		dbg_error("wrong magic");
		tar->err = ENOEXEC;
		return NULL;
	}
	return h;
}

__private int htar_pax(tar_s* tar, htar_s* h, tarent_s* ent){
	unsigned size = strtoul(h->size, NULL, 8);
	char* kv  = (char*)((uintptr_t)h + sizeof(htar_s));
	char* ekv = kv + size;
	while( kv < ekv ){
		unsigned kvsize = strtoul(kv, &kv, 10);
		++kv;
		char* k = kv;
		char* ek = strchr(k, '=');
		if( !ek ){
			tar->err = EINVAL;
			dbg_error("aspected assign: '%s'", kv);
			return -1;
		}
		char* v = ek+1;
		kv = k + kvsize;
		char* ev = kv - 1;
	
		if( !strncmp(k, "size", 4) ){
			ent->size = strtoul(v, NULL, 10);
		}
		else if( !strncmp(k, "path", 4) ){
			if( ent->path ) mem_free(ent->path);
			ent->path = MANY(char, (ev-v) + 1);
			memcpy(ent->path, v, ev - v);
			ent->path[ev-v] = 0;
		}
		else{
			//TODO
		}
	}

	return 0;
}

__private void htar_next_ent(tar_s* tar, tarent_s* ent){
	const size_t rawsize = ROUND_UP(ent->size, sizeof(htar_s));
	tar->loaddr += sizeof(htar_s) + rawsize;
}

__private void htar_next_htar(tar_s* tar, htar_s* h){
	size_t s = strtoul(h->size, NULL, 8);
	const size_t rawsize = ROUND_UP(s, sizeof(htar_s));
	tar->loaddr += sizeof(htar_s) + rawsize;
}

__private void ent_dtor(void* ent){
	tarent_s* e = ent;
	if( e->path ) mem_free(e->path);
}

tarent_s* tar_next(tar_s* tar){
	htar_s* h;
	tarent_s pax = {0};
 	tarent_s* ent;
	
	while( (h = htar_get(tar)) ){
		switch( h->typeflag ){
			case 'g':
				if( htar_pax(tar, h, &tar->global) ) goto ONERR;
				htar_next_htar(tar, h);
			break;
			
			case 'x':
				if( htar_pax(tar, h, &pax) ) goto ONERR;
				htar_next_htar(tar, h);
			break;
			
			case '0' ... '9':
				ent = NEW(tarent_s);
				mem_header(ent)->cleanup = ent_dtor;
				memset(ent, 0, sizeof(tarent_s));
				
				ent->type = h->typeflag - '0';
				if( pax.size > 0 ){
					ent->size = pax.size;
				}
				else if( tar->global.size > 0 ){
					ent->size = tar->global.size;
				}
				else{
					ent->size = strtoul(h->size, NULL, 8);
				}
				ent->data = ent->size ? (void*)(tar->loaddr + sizeof(htar_s)) : NULL;
				
				if( pax.path ){
					ent->path = pax.path;
					pax.path = NULL;
				}
				else if( tar->global.path ){
					ent->path = str_dup(tar->global.path, 0);
				}
				else{
					if( h->prefix[0] ){
						size_t pl = strnlen(h->prefix, sizeof h->prefix);
						size_t nl = strnlen(h->name, sizeof h->name);
						ent->path = MANY(char, pl+nl+2);
						memcpy(ent->path, h->prefix, pl);
						ent->path[pl] = '/';
						memcpy(&ent->path[pl+1], h->name, nl);
						ent->path[pl+nl+1] = 0;
					}
					else{
						size_t nl = strnlen(h->name, sizeof h->name);
						ent->path = MANY(char, nl+1);
						memcpy(ent->path, h->name, nl);
						ent->path[nl] = 0;
					}
				}
				htar_next_ent(tar, ent);
			return ent;

			default:
				dbg_error("unknow type");
				goto ONERR;
			break;
		}
	}
	
ONERR:
	if( pax.path ) mem_free(pax.path);
	return NULL;
}

void tar_close(tar_s* tar){
	if( tar->global.path ){
		mem_free(tar->global.path);
	}
}

int tar_errno(tar_s* tar){
	return tar->err;
}
