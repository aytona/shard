"""Tests for adapter base class — ensures interface contract is enforced."""

import pytest

from adapters.base import BaseAdapter


class TestBaseAdapter:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            BaseAdapter()

    def test_concrete_must_implement_all_methods(self):
        class IncompleteAdapter(BaseAdapter):
            pass

        with pytest.raises(TypeError):
            IncompleteAdapter()

    def test_complete_adapter_instantiates(self):
        class CompleteAdapter(BaseAdapter):
            def read_memory(self, memory_id): return None
            def write_memory(self, memory_id, content): pass
            def list_memories(self, filter_fn=None): return []
            def delete_memory(self, memory_id): pass
            def list_skills(self): return []
            def get_skill_metadata(self, skill_id): return None
            def invoke_skill(self, skill_id, context): return None
            def register_skill(self, skill_id, metadata): pass
            def deregister_skill(self, skill_id): pass
            def list_agents(self): return []
            def send_to_agent(self, agent_id, message): pass
            def on_connect(self): pass
            def on_disconnect(self): pass

        adapter = CompleteAdapter()
        assert adapter is not None
        assert adapter.list_memories() == []
