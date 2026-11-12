"""Shared helpers for Streamlit calculation-result session state."""

# Bump this revision whenever calculation semantics change. Streamlit sessions
# can survive a hot reload; input-only signatures must not bless results created
# by an older calculation implementation.
RESULT_STATE_REVISION = "geolysis-2026-11-12-r2"


def clear_result_state(state, result_key, signature_key):
    """Clear a cached result and its input signature before recalculation."""
    state.pop(result_key, None)
    state.pop(signature_key, None)


def store_result_state(state, result_key, signature_key, result, signature):
    """Store a calculation result together with the exact inputs that produced it."""
    state[result_key] = result
    state[signature_key] = (RESULT_STATE_REVISION, signature)


def read_result_state(state, result_key, signature_key, current_signature):
    """Return (result, is_current) without displaying stale cached results."""
    result = state.get(result_key)
    if result is None:
        return None, False
    return result, state.get(signature_key) == (RESULT_STATE_REVISION, current_signature)
