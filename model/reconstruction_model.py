# coding=utf-8
import os
from itertools import chain

import torch
import torch.nn as nn
import torch.nn.utils
from torch.autograd import Variable
import torch.nn.functional as F
from torch.nn.utils.rnn import pad_packed_sequence, pack_padded_sequence

from model.pointer_net import PointerNet
from model.seq2seq import Seq2SeqModel
import nn_utils
from model.seq2seq_copy import Seq2SeqWithCopy
from asdl.lang.py.py_utils import tokenize_code


class Reconstructor(nn.Module):
    def __init__(self, args, vocab):
        super(Reconstructor, self).__init__()
        self.seq2seq = Seq2SeqWithCopy(src_vocab=vocab.primitive, tgt_vocab=vocab.source,
                                       embed_size=args.embed_size, hidden_size=args.hidden_size,
                                       ptrnet_hidden_dim=args.ptrnet_hidden_dim,
                                       dropout=args.dropout,
                                       use_cuda=args.cuda)

        self.vocab = vocab
        self.args = args

    def _score(self, src_codes, tgt_nls):
        """score examples sorted by code length"""
        args = self.args

        # src_code = [self.tokenize_code(e.tgt_code) for e in examples]
        # tgt_nl = [e.src_sent for e in examples]

        src_code_var = nn_utils.to_input_variable(src_codes, self.vocab.primitive, cuda=args.cuda)
        tgt_nl_var = nn_utils.to_input_variable(tgt_nls, self.vocab.source, cuda=args.cuda, append_boundary_sym=True)

        tgt_token_copy_pos, tgt_token_copy_mask, tgt_token_gen_mask = self.get_generate_and_copy_meta_tensor(src_codes, tgt_nls)

        scores = self.seq2seq(src_code_var,
                              [len(c) for c in src_codes],
                              tgt_nl_var,
                              tgt_token_copy_pos, tgt_token_copy_mask, tgt_token_gen_mask)

        return scores

    def score(self, examples):
        batch_size = len(examples)

        tokenized_codes = [self.tokenize_code(e.tgt_code) for e in examples]

        code_lens = [len(code) for code in tokenized_codes]
        sorted_example_ids = sorted(range(batch_size), key=lambda x: -code_lens[x])

        example_old_pos_map = [-1] * batch_size
        for new_pos, old_pos in enumerate(sorted_example_ids):
            example_old_pos_map[old_pos] = new_pos

        sorted_src_codes = [tokenized_codes[i] for i in sorted_example_ids]
        sorted_tgt_nls = [examples[i].src_sent for i in sorted_example_ids]
        sorted_scores = self._score(sorted_src_codes, sorted_tgt_nls)

        scores = sorted_scores[example_old_pos_map]

        return scores

    def tokenize_code(self, code):
        return tokenize_code(code)

    def get_generate_and_copy_meta_tensor(self, src_codes, tgt_nls):
        tgt_token_copy_pos = []
        tgt_token_copy_mask = []
        tgt_token_gen_mask = []

        tgt_nls = [['<s>'] + x + ['</s>'] for x in tgt_nls]

        max_time_step = max(len(tgt_nl) for tgt_nl in tgt_nls)
        for t in xrange(max_time_step):
            copy_pos_row = []
            copy_mask_row = []
            gen_mask_row = []

            for src_code, tgt_nl in zip(src_codes, tgt_nls):
                copy_pos = copy_mask = gen_mask = 0
                if t < len(tgt_nl):
                    tgt_token = tgt_nl[t]
                    try:
                        copy_pos = src_code.index(tgt_token)
                        copy_mask = 1
                    except ValueError:
                        pass

                    if copy_mask and tgt_token in self.vocab.primitive:
                        gen_mask = 1
                    elif copy_mask and tgt_token not in self.vocab.primitive:
                        gen_mask = 0
                    elif copy_mask == 0 and tgt_token in self.vocab.primitive:
                        gen_mask = 1
                    else:
                        gen_mask = 1

                copy_pos_row.append(copy_pos)
                copy_mask_row.append(copy_mask)
                gen_mask_row.append(gen_mask)

            tgt_token_copy_pos.append(copy_pos_row)
            tgt_token_copy_mask.append(copy_mask_row)
            tgt_token_gen_mask.append(gen_mask_row)

        T = torch.cuda if self.args.cuda else torch
        return Variable(T.LongTensor(tgt_token_copy_pos)), \
               Variable(T.FloatTensor(tgt_token_copy_mask)), \
               Variable(T.FloatTensor(tgt_token_gen_mask))

    def save(self, path):
        dir_name = os.path.dirname(path)
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)

        params = {
            'args': self.args,
            'vocab': self.vocab,
            'state_dict': self.state_dict()
        }

        torch.save(params, path)