"""Shared helpers for Streamlit calculation-result session state."""


def clear_result_state(state, result_key, signature_key):
    """Clear a cached result and its input signature before recalculation."""
    state.pop(result_key, None)
    state.pop(signature_key, None)


def store_result_state(state, result_key, signature_key, result, signature):
    """Store a calculation result together with the exact inputs that produced it."""
    state[result_key] = result
    state[signature_key] = signature


def read_result_state(state, result_key, signature_key, current_signature):
    """Return (result, is_current) without displaying stale cached results."""
    result = state.get(result_key)
    if result is None:
        return None, False
    return result, state.get(signature_key) == current_signature
