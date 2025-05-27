# This file will contain tests for the country module.

import pytest

try:
    from ghostmirror import country
    from ghostmirror.mirror import Mirror
except ImportError:
    from pathlib import Path
    import sys
    project_root = Path(__file__).parent.parent.parent / 'python'
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from ghostmirror import country
    from ghostmirror.mirror import Mirror

# Helper function
def create_test_mirror(country_name: str | None, url="dummy") -> Mirror:
    # In Python 3.9+, country_name can be directly str | None
    # For older versions, it might be just str, and None handled by caller.
    # The Mirror class expects country to be str.
    # If country_name is None, we should pass a default string or handle it.
    # For these tests, let's assume Mirror's country can be None if the type hint allows,
    # or we pass a default like "Unknown" if it must be a string.
    # The Mirror class as defined has `country: str`, so it cannot be None.
    # We'll use "Unknown" or a specific string if None is passed to helper.
    
    # The Mirror class's __init__ expects a string for country.
    # If country_name is None, use "Unknown" or some other default.
    # However, for testing `filter_mirrors_by_country` with a Mirror object
    # that might conceptually have a "None" country, the test setup needs care.
    # Let's assume the `Mirror` object's `country` attribute IS a string.
    # A `None` passed to this helper will be converted to "NoneCountry" for testing.
    
    effective_country = country_name if country_name is not None else "NoneCountryTest" # Make it distinct
    m = Mirror(url=url, country=effective_country, arch="x86_64")
    return m

# Tests for filter_mirrors_by_country
def test_filter_no_countries_specified():
    mirrors = [create_test_mirror("USA"), create_test_mirror("Canada")]
    assert country.filter_mirrors_by_country(mirrors, []) == mirrors
    assert country.filter_mirrors_by_country(mirrors, None) == mirrors

def test_filter_basic_filtering():
    m_usa = create_test_mirror("USA")
    m_canada = create_test_mirror("Canada")
    m_germany = create_test_mirror("Germany")
    mirrors = [m_usa, m_canada, m_germany]
    
    filtered = country.filter_mirrors_by_country(mirrors, ["USA", "Germany"])
    assert m_usa in filtered
    assert m_germany in filtered
    assert m_canada not in filtered
    assert len(filtered) == 2

def test_filter_no_matches():
    mirrors = [create_test_mirror("USA"), create_test_mirror("Canada")]
    assert country.filter_mirrors_by_country(mirrors, ["Germany"]) == []

def test_filter_empty_mirror_list():
    assert country.filter_mirrors_by_country([], ["USA"]) == []

def test_filter_with_none_country_in_mirrors():
    # The Mirror class expects country: str. So a Mirror object won't have `country=None`.
    # It might have `country="Unknown"` or `country=""`.
    # The helper `create_test_mirror` converts None to "NoneCountryTest".
    m_none_country = create_test_mirror(None) # Effectively "NoneCountryTest"
    m_usa = create_test_mirror("USA")
    mirrors = [m_none_country, m_usa]
    
    # Filter for "USA"
    filtered_usa = country.filter_mirrors_by_country(mirrors, ["USA"])
    assert m_usa in filtered_usa
    assert m_none_country not in filtered_usa
    
    # Filter for "NoneCountryTest"
    filtered_none = country.filter_mirrors_by_country(mirrors, ["NoneCountryTest"])
    assert m_none_country in filtered_none
    assert m_usa not in filtered_none

    # Test with a Mirror object having an empty string country
    m_empty_str_country = Mirror(url="empty_country_url", country="", arch="x86_64")
    mirrors_with_empty = [m_empty_str_country, m_usa]
    filtered_empty = country.filter_mirrors_by_country(mirrors_with_empty, [""])
    assert m_empty_str_country in filtered_empty
    assert m_usa not in filtered_empty
    
    # Test filtering for a non-empty country when an empty string country mirror exists
    filtered_usa_with_empty = country.filter_mirrors_by_country(mirrors_with_empty, ["USA"])
    assert m_usa in filtered_usa_with_empty
    assert m_empty_str_country not in filtered_usa_with_empty


# Tests for get_country_list
def test_get_list_basic():
    mirrors = [create_test_mirror("USA"), create_test_mirror("Canada")]
    expected = sorted(["USA", "Canada"])
    assert country.get_country_list(mirrors) == expected

def test_get_list_with_duplicates_none_empty_string():
    # Helper create_test_mirror converts None to "NoneCountryTest"
    m_none = create_test_mirror(None) # -> "NoneCountryTest"
    m_empty = Mirror(url="empty", country="", arch="x86_64")
    m_whitespace = Mirror(url="whitespace", country="   ", arch="x86_64")
    
    mirrors = [
        create_test_mirror("USA"),
        create_test_mirror("Canada"),
        create_test_mirror("USA"), # Duplicate
        m_none,
        m_empty,         # Empty string country
        m_whitespace     # Whitespace only country
    ]
    # Expected: "Canada", "NoneCountryTest", "USA". Empty and whitespace-only are filtered out.
    expected = sorted(["Canada", "NoneCountryTest", "USA"])
    actual = country.get_country_list(mirrors)
    assert actual == expected

def test_get_list_empty_input():
    assert country.get_country_list([]) == []

pass # Final pass for the file.
