"""Tests for cache key generation — verifies no memory addresses in keys."""

from datetime import date, datetime
from decimal import Decimal

import pytest
from vnbroker.core.utils.cache import TTLCache, cached_listing, get_listing_cache


class _FakeObj:
    """Simulates a domain object whose str() includes a memory address."""
    def __str__(self):
        return f"<FakeObj object at 0x{id(self):016X}>"


class _OtherObj:
    """A second domain object type, also with an address in str()."""
    def __str__(self):
        return f"<OtherObj object at 0x{id(self):016X}>"


@pytest.fixture
def cache():
    return TTLCache(ttl_seconds=60, max_size=10, name="test")


@pytest.fixture
def listing_cache():
    """The process-wide listing cache, cleared around each test."""
    shared = get_listing_cache()
    shared.clear()
    yield shared
    shared.clear()


# ── _make_key tests ──────────────────────────────────────────────────────────

def test_cache_key_no_object_id(cache):
    """No memory address may leak into the key.

    Asserted behaviourally, not by string literal: two *different* instances
    of the same class must produce the SAME key, which is only true if the
    address does not participate. (An earlier version of this test asserted
    the literal ``"object at" not in key``, which only held because the
    encoder dropped objects to a bare type name.)
    """
    obj = _FakeObj()
    key = cache._make_key("func_name", obj, "arg1")
    assert "0x" not in key
    assert "0000" not in key.split("obj:")[-1]
    assert key == cache._make_key("func_name", _FakeObj(), "arg1")


def test_cache_key_consistent(cache):
    """Same primitive args must produce the same key."""
    key1 = cache._make_key("func", "a", 1, 2.5, True, None)
    key2 = cache._make_key("func", "a", 1, 2.5, True, None)
    assert key1 == key2


def test_cache_key_different_args(cache):
    """Different args must produce different keys."""
    key1 = cache._make_key("func", "a")
    key2 = cache._make_key("func", "b")
    assert key1 != key2


def test_cache_key_kwargs_sorted(cache):
    """Kwargs order must not affect the key."""
    key1 = cache._make_key("func", x=1, y=2)
    key2 = cache._make_key("func", y=2, x=1)
    assert key1 == key2


def test_cache_key_filters_non_primitive_kwargs(cache):
    """A kwarg must survive into the key, whatever its value's type."""
    obj = _FakeObj()
    key = cache._make_key("func", bad=obj, good="ok")
    assert "0x" not in key
    # The value is present and reachable: two calls differing only in `good`
    # must not share an entry, while the same call must still hit.
    assert "ok" in key
    cache.set(cache._make_key("func", bad=obj, good="ok"), "P1")
    assert cache.get(cache._make_key("func", bad=obj, good="no")) is None
    assert cache.get(cache._make_key("func", bad=obj, good="ok")) == "P1"


# ── Cache hit / miss integration ─────────────────────────────────────────────

def test_cache_hit_after_fix(cache):
    """Cache must hit when called twice with same primitive args."""
    call_count = 0

    def expensive(x):
        nonlocal call_count
        call_count += 1
        return x * 2

    key = cache._make_key("expensive", 5)

    # First call — miss
    result1 = cache.get(key)
    assert result1 is None
    cache.set(key, expensive(5))

    # Second call — hit
    result2 = cache.get(key)
    assert result2 == 10
    assert call_count == 1  # function called only once


def test_cache_miss_different_args(cache):
    """Different args must produce a cache miss."""
    cache.set(cache._make_key("f", 1), "one")
    assert cache.get(cache._make_key("f", 2)) is None


def test_cache_stats_hit_rate(cache):
    """Stats should reflect hits and misses correctly."""
    key = cache._make_key("f", "x")
    cache.get(key)          # miss
    cache.set(key, 42)
    cache.get(key)          # hit
    stats = cache.stats()
    assert stats["hit_count"] == 1
    assert stats["total_count"] == 2
    assert stats["hit_rate"] == 0.5


# ── VN-2 / AC-9: no argument may be silently dropped from the key ───────────
#
# `_make_key` used to keep only str/int/float/bool/None arguments, so every
# call whose arguments were `date`, `list` or `dict` produced the SAME key and
# the cache served one call's payload for another's arguments.

def test_date_arguments_do_not_collide(cache):
    """Two different dates must not produce the same key."""
    old = cache._make_key("all_symbols", date(2024, 1, 1))
    new = cache._make_key("all_symbols", date(2026, 10, 8))
    assert old != new


def test_list_order_is_part_of_the_key(cache):
    """A list is ordered: ['ACB','VNM'] must differ from ['VNM','ACB']."""
    assert cache._make_key("f", ["ACB", "VNM"]) != cache._make_key("f", ["VNM", "ACB"])


def test_dict_values_are_part_of_the_key(cache):
    """A dict's values must not be dropped from the key."""
    assert cache._make_key("f", {"a": 1}) != cache._make_key("f", {"a": 2})


def test_list_and_tuple_are_distinguished(cache):
    """A list and a tuple with the same items are different arguments."""
    assert cache._make_key("f", ["ACB"]) != cache._make_key("f", ("ACB",))


def test_datetime_and_date_are_distinguished(cache):
    """A datetime must not share the key of the date it falls on."""
    day = date(2024, 1, 1)
    moment = datetime(2024, 1, 1, 9, 30)
    assert cache._make_key("f", day) != cache._make_key("f", moment)


def test_nested_arguments_are_distinguished(cache):
    """Structure inside an argument must still change the key."""
    assert cache._make_key("f", ["a", {"b": 1}]) != cache._make_key("f", ["a", {"b": 2}])
    assert cache._make_key("f", {"a": ["x"]}) != cache._make_key("f", {"a": ["y"]})


def test_kwarg_container_values_are_distinguished(cache):
    """The rule applies to kwargs exactly as it does to positional args."""
    assert cache._make_key("f", symbols=["ACB"]) != cache._make_key("f", symbols=["VNM"])


def test_unknown_object_types_are_distinguished_without_addresses(cache):
    """Domain objects collapse to their type name, never to a memory address."""
    key = cache._make_key("f", _FakeObj())
    assert "0x" not in key
    assert cache._make_key("f", _FakeObj()) != cache._make_key("f", _OtherObj())


def test_same_arguments_still_produce_one_stable_key(cache):
    """Positive case: equal arguments must keep producing an equal key."""
    assert cache._make_key("f", date(2024, 1, 1), ["ACB"], {"a": 1}) == \
        cache._make_key("f", date(2024, 1, 1), ["ACB"], {"a": 1})


def test_cache_still_hits_for_repeated_non_primitive_arguments(cache):
    """Positive case: the cache must still hit, so the fix costs no reuse."""
    calls = []

    def expensive(*_args, **_kwargs):
        calls.append(1)
        return "computed"

    def cached(*args, **kwargs):
        key = cache._make_key("expensive", *args, **kwargs)
        hit = cache.get(key)
        if hit is not None:
            return hit
        result = expensive(*args, **kwargs)
        cache.set(key, result)
        return result

    day = date(2024, 1, 1)
    symbols = ["ACB", "VNM"]

    assert cached(day, symbols=symbols) == "computed"
    assert cached(day, symbols=symbols) == "computed"
    assert len(calls) == 1  # second call served from the cache

    # Different arguments must still miss.
    assert cached(date(2026, 10, 8), symbols=symbols) == "computed"
    assert cached(day, symbols=["VNM", "ACB"]) == "computed"
    assert len(calls) == 3


def test_cache_does_not_serve_another_dates_payload(cache):
    """End-to-end corruption check: write under one date, read under another."""
    cache.set(cache._make_key("all_symbols", date(2024, 1, 1)), "payload-2024-01-01")

    assert cache.get(cache._make_key("all_symbols", date(2026, 10, 8))) is None
    assert cache.get(cache._make_key("all_symbols", date(2024, 1, 1))) == "payload-2024-01-01"


def test_cache_does_not_serve_another_list_order_payload(cache):
    """End-to-end corruption check for list ordering."""
    cache.set(cache._make_key("all_symbols", ["ACB", "VNM"]), "payload-acb-vnm")

    assert cache.get(cache._make_key("all_symbols", ["VNM", "ACB"])) is None
    assert cache.get(cache._make_key("all_symbols", ["ACB", "VNM"])) == "payload-acb-vnm"


def test_cache_does_not_serve_another_dict_payload(cache):
    """End-to-end corruption check for dict values."""
    cache.set(cache._make_key("all_symbols", {"a": 1}), "payload-a=1")

    assert cache.get(cache._make_key("all_symbols", {"a": 2})) is None
    assert cache.get(cache._make_key("all_symbols", {"a": 1})) == "payload-a=1"


# ── Same-named methods of different providers must not share a cache entry ───
#
# Found while fixing VN-2, NOT part of AC-9: `cached_listing` keyed on
# `func.__name__` only, and every listing cache is the SAME global object. So
# `kbs.Listing.all_symbols` (explorer/kbs/listing.py:66) and
# `vci.Listing.all_symbols` (explorer/vci/listing.py:49) — two providers whose
# classes are both named `Listing` — shared one entry, and whichever provider
# was called first served its DataFrame to the other for LISTING_CACHE_TTL.

def _stub_provider_method(module_name, class_name, payload, calls):
    """Build a cached_listing-decorated method standing in for a provider."""
    def all_symbols(self=None):
        calls.append(module_name)
        return payload

    all_symbols.__name__ = "all_symbols"
    all_symbols.__qualname__ = f"{class_name}.all_symbols"
    all_symbols.__module__ = module_name
    return cached_listing(ttl_seconds=60)(all_symbols)


def test_cached_listing_does_not_cross_serve_same_named_provider_methods(listing_cache):
    """Two providers' `all_symbols` must not read each other's cache entry."""
    calls = []
    kbs = _stub_provider_method(
        "vnbroker.explorer.kbs.listing", "Listing", "FROM-KBS", calls
    )
    vci = _stub_provider_method(
        "vnbroker.explorer.vci.listing", "Listing", "FROM-VCI", calls
    )

    assert kbs() == "FROM-KBS"
    assert vci() == "FROM-VCI"
    assert calls == [
        "vnbroker.explorer.kbs.listing",
        "vnbroker.explorer.vci.listing",
    ]


def test_cached_listing_does_not_cross_serve_across_cache_types(listing_cache):
    """The same method name in the industry cache stays separate from listing."""
    from vnbroker.core.utils.cache import cached_industry, get_industry_cache

    industry_cache = get_industry_cache()
    industry_cache.clear()
    try:
        calls = []

        def symbols_by_industries(self=None):
            calls.append("listing")
            return "FROM-LISTING"

        symbols_by_industries.__name__ = "shared_name"
        symbols_by_industries.__qualname__ = "Listing.shared_name"
        symbols_by_industries.__module__ = "vnbroker.explorer.kbs.listing"

        def shared_name(self=None):
            calls.append("industry")
            return "FROM-INDUSTRY"

        shared_name.__name__ = "shared_name"
        shared_name.__qualname__ = "Industry.shared_name"
        shared_name.__module__ = "vnbroker.explorer.kbs.industry"

        listing_fn = cached_listing(ttl_seconds=60)(symbols_by_industries)
        industry_fn = cached_industry(ttl_seconds=60)(shared_name)

        assert listing_fn() == "FROM-LISTING"
        assert industry_fn() == "FROM-INDUSTRY"
        assert calls == ["listing", "industry"]
    finally:
        industry_cache.clear()


def test_cached_listing_still_caches_the_same_provider_method(listing_cache):
    """Positive case: namespacing must not cost the cache its hits."""
    calls = []
    kbs = _stub_provider_method(
        "vnbroker.explorer.kbs.listing", "Listing", "FROM-KBS", calls
    )

    assert kbs() == "FROM-KBS"
    assert kbs() == "FROM-KBS"
    assert calls == ["vnbroker.explorer.kbs.listing"]  # second call was a hit


def test_cached_listing_still_honours_arguments(listing_cache):
    """Positive case: different arguments of the same method still miss."""
    calls = []

    def all_symbols(self=None, include_derivatives=False):
        calls.append(include_derivatives)
        return f"DERIV={include_derivatives}"

    all_symbols.__name__ = "all_symbols"
    all_symbols.__qualname__ = "SSIListing.all_symbols"
    all_symbols.__module__ = "vnbroker.explorer.ssi.listing"
    cached = cached_listing(ttl_seconds=60)(all_symbols)

    assert cached(include_derivatives=False) == "DERIV=False"
    assert cached(include_derivatives=True) == "DERIV=True"
    assert cached(include_derivatives=False) == "DERIV=False"
    assert calls == [False, True]  # third call was a hit


# ── MAJOR-3: the encoder denied an invariant it did not provide ──────────────
#
# The old docstring claimed "Every branch keeps the value's information, so
# different arguments cannot share a token". Two branches broke it:
#
#   * `if isinstance(value, PRIMITIVES): return str(value)` — `str()` and
#     `None`/`int` both fall through with no type label, so `None` vs `"None"`
#     and `0` vs `"0"` produced one key.
#   * `return type(value).__name__` — collapsed EVERY object to its class
#     name, so two DataFrames, two Decimals and two domain objects shared one
#     entry, and the cache served one call's payload for another's arguments.
#
# Severity: no current caller is harmed. All 12 real @cached_listing /
# @cached_industry functions accept only str/bool/Optional[str]. This is a
# wrong contract plus an armed trap, not an incident in progress.

class _Configured:
    """A domain object whose two instances differ only in their attributes."""

    def __init__(self, tag):
        self.tag = tag


class _Slotted:
    """Same, but its state lives in __slots__ rather than __dict__."""

    __slots__ = ("tag",)

    def __init__(self, tag):
        self.tag = tag


# ── 1. The primitive branch needs a type label ───────────────────────────────

def test_none_and_the_string_none_do_not_collide(cache):
    """`None` and `"None"` are different arguments, not the same one."""
    assert cache._make_key("f", None) != cache._make_key("f", "None")


@pytest.mark.parametrize("text", ["0", "1"])
def test_int_and_the_matching_string_do_not_collide(cache, text):
    """`0` and `"0"` are different arguments."""
    assert cache._make_key("f", int(text)) != cache._make_key("f", text)


def test_values_that_compare_equal_still_get_different_keys(cache):
    """`1 == True == 1.0`, so `==` cannot be the thing that keeps keys apart."""
    assert cache._make_key("f", 1) != cache._make_key("f", True)
    assert cache._make_key("f", 1) != cache._make_key("f", 1.0)
    assert cache._make_key("f", True) != cache._make_key("f", 1.0)


def test_primitive_type_labels_survive_in_the_key(cache):
    """The key must record the type, so the separation is not accidental."""
    key = cache._make_key("f", None, True, 1, 1.0)
    assert "none" in key
    assert "bool:True" in key
    assert "int:1" in key
    assert "float:1.0" in key


# ── 2. The object branch must stop collapsing to the bare class name ─────────

def test_dataframes_with_different_contents_do_not_collide(cache):
    """Two different DataFrames are two different arguments."""
    import pandas as pd

    left = pd.DataFrame({"a": [1, 2, 3]})
    right = pd.DataFrame({"a": [9, 9, 9]})
    assert cache._make_key("f", left) != cache._make_key("f", right)


def test_dataframes_with_equal_contents_still_share_a_key(cache):
    """Positive control: the DataFrame fix must not cost the cache its hits."""
    import pandas as pd

    left = pd.DataFrame({"a": [1, 2, 3]})
    right = pd.DataFrame({"a": [1, 2, 3]})
    assert cache._make_key("f", left) == cache._make_key("f", right)


def test_decimals_with_different_values_do_not_collide(cache):
    """`Decimal('1')` and `Decimal('2')` are different arguments."""
    assert cache._make_key("f", Decimal("1")) != cache._make_key("f", Decimal("2"))


def test_objects_with_different_state_do_not_collide(cache):
    """Two instances of one class differing only in attributes must differ."""
    assert cache._make_key("f", _Configured("a")) != cache._make_key("f", _Configured("b"))


def test_slotted_objects_with_different_state_do_not_collide(cache):
    """State kept in __slots__ counts as state too."""
    assert cache._make_key("f", _Slotted("a")) != cache._make_key("f", _Slotted("b"))


def test_objects_with_equal_state_still_share_a_key(cache):
    """Positive control: a masked repr alone would make every instance unique.

    A bare `re.sub(r"0x[0-9a-f]+", ...)` over `repr()` yields the same token
    for every instance, which would empty the cache for repeated calls.
    """
    assert cache._make_key("f", _Configured("a")) == cache._make_key("f", _Configured("a"))
    assert cache._make_key("f", _Slotted("a")) == cache._make_key("f", _Slotted("a"))


def test_uppercase_hex_addresses_are_masked_too(cache):
    """CPython prints addresses in UPPERCASE hex; a lowercase-only regex misses.

    ``re.sub(r"0x[0-9a-f]+", ...)`` stops at the first ``E`` of
    ``0x000001E65D248D70`` and leaves ``E65D248D70`` behind, so every instance
    would still look unique and the cache would never hit.
    """
    obj = _FakeObj()  # its __str__ renders 0x{id(self):016X}
    assert "0000" not in cache._make_key("f", obj)
    assert cache._make_key("f", obj) == cache._make_key("f", _FakeObj())


def test_object_keys_carry_no_address_at_all(cache):
    """Nothing address-shaped may survive in any branch of the key."""
    for obj in (_FakeObj(), _OtherObj(), _Configured("z"), _Slotted("z")):
        key = cache._make_key("f", obj)
        assert "0x" not in key
        assert "<addr>" in key


# ── 3. The wrong-payload read, end to end ────────────────────────────────────

def test_cache_does_not_serve_another_dataframes_payload(cache):
    """The damage the audit demonstrated: write under df1, read under df2."""
    import pandas as pd

    left = pd.DataFrame({"a": [1, 2, 3]})
    right = pd.DataFrame({"a": [9, 9, 9]})
    cache.set(cache._make_key("f", left), "PAYLOAD_FOR_LEFT")

    assert cache.get(cache._make_key("f", right)) is None
    assert cache.get(cache._make_key("f", left)) == "PAYLOAD_FOR_LEFT"


def test_cache_does_not_serve_another_objects_payload(cache):
    """Same corruption check for the object branch."""
    cache.set(cache._make_key("f", _Configured("a")), "PAYLOAD_A")

    assert cache.get(cache._make_key("f", _Configured("b"))) is None
    assert cache.get(cache._make_key("f", _Configured("a"))) == "PAYLOAD_A"


def test_cache_does_not_serve_another_decimals_payload(cache):
    """Same corruption check for a value type behind a custom repr."""
    cache.set(cache._make_key("f", Decimal("1")), "PAYLOAD_1")

    assert cache.get(cache._make_key("f", Decimal("2"))) is None
    assert cache.get(cache._make_key("f", Decimal("1"))) == "PAYLOAD_1"


def test_cache_round_trip_for_every_collision_pair(cache):
    """One round trip per pair the audit listed: hit on equal, miss on unequal."""
    import pandas as pd

    pairs = [
        (None, "None"),
        (0, "0"),
        (1, "1"),
        (1, True),
        (1, 1.0),
        (pd.DataFrame({"a": [1, 2, 3]}), pd.DataFrame({"a": [9, 9, 9]})),
        (Decimal("1"), Decimal("2")),
        (_Configured("a"), _Configured("b")),
    ]
    for index, (left, right) in enumerate(pairs):
        cache.set(cache._make_key("f", left), f"PAYLOAD-{index}")
        assert cache.get(cache._make_key("f", right)) is None, (left, right)
        assert cache.get(cache._make_key("f", left)) == f"PAYLOAD-{index}", (left, right)


# ── 4. dict insertion order leaked into the token ────────────────────────────

def test_dict_insertion_order_does_not_change_the_key(cache):
    """`{1:'x','1':'y'}` built in two orders must produce one key.

    Sorting happened AFTER encoding, and both keys encoded to the same token
    (`str(1)` and `str('1')` are both `'1'`), so the stable sort kept
    insertion order and the two dicts split into two entries.
    """
    first = cache._make_key("f", {1: "x", "1": "y"})
    second = cache._make_key("f", {"1": "y", 1: "x"})
    assert first == second


def test_lookalike_dict_keys_both_survive_the_sort(cache):
    """They must also still be distinguishable from each other by value."""
    assert cache._make_key("f", {1: "x", "1": "y"}) != cache._make_key("f", {1: "x", "1": "z"})
    assert cache._make_key("f", {1: "x"}) != cache._make_key("f", {"1": "x"})


# ── 5. The positional/keyword separator was separated by luck ────────────────

def test_positional_and_keyword_arguments_are_separated(cache):
    """`_make_key('x', 1)` and `_make_key(x=1)` must not share a key."""
    assert cache._make_key("x", 1) != cache._make_key(x=1)


def test_separator_characters_inside_a_value_cannot_forge_a_field(cache):
    """A value containing `|`, `=` or `:` must not be read as a field boundary.

    Before the fix, `_make_key("x", 1)` produced `'x|1'` and `_make_key(x=1)`
    produced `'x=1'` — separated only because neither argument happened to
    contain the separator. Length prefixes make the split structural.
    """
    assert cache._make_key("x", 1) != cache._make_key("x|1")
    assert cache._make_key("x", 1) != cache._make_key("x=1")
    assert cache._make_key("x", 1) != cache._make_key("p5:str:x|p5:int:1")
    assert cache._make_key(x=1) != cache._make_key("k1:x=5:int:1")
    assert cache._make_key("v", x=1) != cache._make_key("v", **{"x|1": 1})
    assert cache._make_key("v", x=1) != cache._make_key("v", **{"x=1": 1})


def test_one_argument_containing_a_separator_is_not_two_arguments(cache):
    """`("x|1",)` is one argument; `("x", "1")` is two."""
    assert cache._make_key("x|1") != cache._make_key("x", "1")


# ── 6. Determinism and robustness of the encoder itself ──────────────────────

def test_self_referential_container_does_not_break_key_generation(cache):
    """A cyclic argument must not raise RecursionError while a key is built."""
    loop = []
    loop.append(loop)
    key = cache._make_key("f", loop)
    assert key == cache._make_key("f", loop)  # still deterministic

    mapping = {}
    mapping["self"] = mapping
    assert cache._make_key("f", mapping) == cache._make_key("f", mapping)


def test_key_generation_survives_a_broken_repr(cache):
    """One object with a raising __repr__ must not take the cache down."""
    class Explodes:
        def __repr__(self):
            raise RuntimeError("boom")

        def __str__(self):
            return "Explodes"

    key = cache._make_key("f", Explodes())
    assert key == cache._make_key("f", Explodes())


def test_oversized_object_token_is_digested_not_truncated_away(cache):
    """A long repr must not become a multi-megabyte dict key.

    The digest must still separate two different objects, and must not depend
    on `hash()`, which is salted per process for str.
    """
    class Long:
        def __init__(self, filler):
            self.filler = filler

        def __repr__(self):
            return f"<Long filler={self.filler * 5000}>"

    left_key = cache._make_key("f", Long("L"))
    assert len(left_key) < 8192
    assert "blake2b128" in left_key
    assert left_key != cache._make_key("f", Long("R"))
    assert left_key == cache._make_key("f", Long("L"))


def test_object_repr_is_the_ceiling_on_discrimination(cache):
    """KNOWN LIMIT, pinned on purpose — this is not fixed, only documented.

    The object branch is exactly as discriminating as the object's own
    ``__repr__``. pandas truncates a frame past ``display.max_rows``, so two
    frames that differ only *below* that row share a token. Nothing in this
    repo pushes a DataFrame through `_make_key` (all 12 real cached listing /
    industry functions take str/bool/Optional[str]), so this is a bound on
    the contract rather than a live bug — but if a caller ever does cache a
    frame, this is the assertion that will have to change.
    """
    import pandas as pd

    short = pd.DataFrame({"a": [1, 2, 3]})
    tall = pd.DataFrame({"a": list(range(2000))})
    tall_edited_deep = pd.DataFrame({"a": list(range(2000))})
    tall_edited_deep.iloc[100, 0] = -1  # inside the '...' the repr elides

    assert cache._make_key("f", short) != cache._make_key("f", tall)
    # Same rows shown by repr(), one value edited below the truncation point:
    assert cache._make_key("f", tall) == cache._make_key("f", tall_edited_deep)


def test_no_key_contains_a_memory_address_for_any_argument_shape(cache):
    """Catch-all: scan the key for anything address-shaped."""
    import pandas as pd

    args = [
        _FakeObj(), _OtherObj(), _Configured("q"), _Slotted("q"),
        pd.DataFrame({"a": [1, 2, 3]}), Decimal("1"), _ExplodingRepr(),
    ]
    for value in args:
        for key in (
            cache._make_key("f", value),
            cache._make_key("f", "prefix", value, "suffix"),
            cache._make_key("f", kw=value),
            cache._make_key("f", [value]),
            cache._make_key("f", {"k": value}),
        ):
            assert "0x" not in key, (value, key)


class _ExplodingRepr:
    """Stand-in for a third-party object whose __repr__ is unusable."""

    def __repr__(self):
        raise ValueError("cannot render")

    def __str__(self):
        return "ExplodingRepr"
