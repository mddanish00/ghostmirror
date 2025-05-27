"""
This module provides utility functions for handling country-specific operations
related to Arch Linux mirrors, such as filtering a list of mirrors by specified
countries and extracting a unique, sorted list of countries from a mirror list.
"""

from .mirror import Mirror # Import Mirror class for type hinting

def filter_mirrors_by_country(mirrors: list[Mirror], countries: list[str]) -> list[Mirror]:
    """
    Filters a list of Mirror objects, returning only those located in the specified countries.

    The comparison is case-insensitive. If the `countries` list is empty or None,
    the original list of mirrors is returned unmodified.

    Args:
        mirrors (list[Mirror]): A list of `Mirror` objects to be filtered.
        countries (list[str]): A list of country names (strings). Mirrors whose
                               `country` attribute matches any of these names
                               (case-insensitively) will be included.

    Returns:
        list[Mirror]: A new list containing only the `Mirror` objects that match
                      the specified country criteria. Returns the original `mirrors`
                      list if `countries` is empty or `None`.
    """
    if not countries: # If no countries are specified for filtering, return all mirrors
        return mirrors

    # Normalize specified country names to lowercase for case-insensitive matching
    lowercase_countries = [country.lower() for country in countries]
    
    filtered_mirrors = []
    for mirror_obj in mirrors:
        # Check if the mirror's country (after converting to lowercase) is in the target list.
        # Ensures that mirror_obj.country is not None and not an empty string before calling .lower().
        if mirror_obj.country and mirror_obj.country.lower() in lowercase_countries:
            filtered_mirrors.append(mirror_obj)
            
    return filtered_mirrors

def get_country_list(mirrors: list[Mirror]) -> list[str]:
    """
    Extracts a unique, sorted list of country names from a list of Mirror objects.

    This function iterates through the provided list of mirrors, collects all unique
    country names, and returns them in alphabetical order. Country names that are
    None, empty strings, or consist only of whitespace are filtered out.

    Args:
        mirrors (list[Mirror]): A list of `Mirror` objects from which to extract
                                country names.

    Returns:
        list[str]: A sorted list of unique country names found in the mirrors.
                   Returns an empty list if the input `mirrors` list is empty
                   or if no valid country names are found.
    """
    if not mirrors: # Handle empty input list
        return []

    country_names = set() # Use a set to automatically handle deduplication
    for mirror_obj in mirrors:
        country_val = mirror_obj.country 
        # Add to set only if country_val is a non-empty string (after stripping whitespace)
        if country_val and country_val.strip(): 
            country_names.add(country_val)
            
    # Convert the set of unique country names to a list and sort it alphabetically
    return sorted(list(country_names))
```
