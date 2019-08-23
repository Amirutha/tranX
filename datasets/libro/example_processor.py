from common.registerable import Registrable
from datasets.utils import ExampleProcessor

from asdl.asdl_ast import AbstractSyntaxTree


@Registrable.register('libro_example_processor')
class LibroExampleProcessor(ExampleProcessor):
    def __init__(self, transition_system):
        self.transition_system = transition_system

    def pre_process_utterance(self, utterance):
        canonical_utterance_tokens, const_index_dict, type_index_dict = q_process(utterance)

        slot2entity_map = dict()
        for typed_entity, idx in const_index_dict.items():
            entity_name, entity_type = typed_entity.split(':')
            slot2entity_map['%s%d' % (entity_type, idx)] = typed_entity

        return canonical_utterance_tokens, slot2entity_map

    def post_process_hypothesis(self, hyp, meta_info, utterance=None):
        """traverse the AST and replace slot ids with original strings"""
        slot2entity_map = meta_info

        def _travel(root):
                for field in root.fields:
                    if self.transition_system.grammar.is_primitive_type(field.type):
                        slot_name = field.value
                        if slot_name in slot2entity_map:
                            field.value = slot2entity_map[slot_name]
                    else:
                        for val in field.as_value_list:
                            _travel(val)

        _travel(hyp.tree)
        hyp.code = self.transition_system.ast_to_surface_code(hyp.tree)

def q_process(_q):
  m2e_dict = {}
  e2type_dict = {}
  is_successful = True
  q = _q
  # tokenize q
  q = ' '.join(q.split(' '))
  # find entities in q, and replace them with type_id
  const_index_dict = {}
  type_index_dict = {}
  while True:
    q_list = list(filter(lambda x: len(x) > 0, ' '.join(map(lambda x: x, q.split(' '))).split(' ')))
    found_flag=False
    for n in range(5, 0, -1):
      if len(q_list) >= n:
        for i in range(0, len(q_list)-n+1):
          m = ' '.join(q_list[i:i+n])
          if m in m2e_dict:
            e = m2e_dict[m]
            t = e2type_dict[e]
            if e not in const_index_dict:
              type_index_dict[t] = type_index_dict.get(t, -1) + 1
              const_index_dict[e] = type_index_dict[t]
            q = q.replace(' %s ' % (m,), ' %s%d ' % (t, const_index_dict[e]))
            found_flag=True
            break
        if found_flag:
          break
    if not found_flag:
      break

  q_list = list(filter(lambda x: len(x) > 0, ' '.join(map(lambda x: x, q.split(' '))).split(' ')))

  return q_list, const_index_dict, type_index_dict


