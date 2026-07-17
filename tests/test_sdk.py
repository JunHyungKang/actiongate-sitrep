import pytest

from sitrep_agent import sdk


@pytest.mark.asyncio
async def test_daily_llm_call_limit_blocks_excess_requests(monkeypatch):
    monkeypatch.setattr(sdk, "LLM_MAX_DAILY_CALLS", 1)
    monkeypatch.setattr(sdk, "_llm_usage_day", "")
    monkeypatch.setattr(sdk, "_llm_usage_count", 0)

    await sdk._reserve_llm_call()

    with pytest.raises(RuntimeError, match="daily call limit"):
        await sdk._reserve_llm_call()


@pytest.mark.asyncio
async def test_llm_input_limit_blocks_before_network_call(monkeypatch):
    monkeypatch.setattr(sdk, "LLM_MAX_INPUT_CHARS", 5)

    with pytest.raises(RuntimeError, match="input limit"):
        await sdk.LLM("unused").complete(system="123", prompt="456")
