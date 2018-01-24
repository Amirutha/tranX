# coding=utf-8
from __future__ import print_function

import sys
import traceback

import os
import astor
import torch
import torch.nn as nn
import torch.nn.utils
from torch.autograd import Variable
import torch.nn.functional as F
from torch.nn.utils.rnn import pad_packed_sequence, pack_padded_sequence

from asdl.lang.py.py_asdl_helper import asdl_ast_to_python_ast
from components.dataset import Example
from parser import *
from reconstruction_model import *


class StructVAE(nn.Module):
    def __init__(self, encoder, decoder, prior, args):
        super(StructVAE, self).__init__()

        self.encoder = encoder
        self.decoder = decoder
        self.prior = prior

        self.args = args

        # for baseline
        self.b_x_l1 = nn.Linear(args.hidden_size, 20)
        self.b_x_l2 = nn.Linear(20, 1, bias=False)
        self.b = nn.Parameter(torch.FloatTensor(1))

        # initialize baseline to be a small negative number
        self.b.data.fill_(-20.)

    def get_unsupervised_loss(self, examples):
        samples, sample_scores, b_x = self.infer(examples)

        reconstruction_scores = self.decoder.score(samples)

        # compute prior probability
        prior_scores = self.prior([e.tgt_code for e in samples])
        prior_scores = Variable(b_x.data.new(prior_scores))

        raw_learning_signal = reconstruction_scores - self.args.alpha * (sample_scores - prior_scores)
        learning_signal = raw_learning_signal.detach() - self.b - b_x

        encoder_loss = -learning_signal.detach() * sample_scores
        decoder_loss = -reconstruction_scores

        # compute baseline loss
        baseline_loss = learning_signal ** 2

        meta_data = {'samples': samples,
                     'reconstruction_scores': reconstruction_scores,
                     'raw_learning_signal': raw_learning_signal,
                     'learning_signal': learning_signal,
                     'baseline': self.b + b_x}

        return encoder_loss, decoder_loss, baseline_loss, meta_data

    def infer(self, examples):
        # currently use beam search as sampling method
        # set model to evaluation model for beam search, make sure dropout is properly behaving!
        was_training = self.encoder.training
        self.encoder.eval()

        hypotheses = [self.encoder.parse(e.src_sent, beam_size=self.args.sample_size) for e in examples]

        if was_training: self.encoder.train()

        # some source may not have corresponding samples, so we only retain those that have sampled logical forms
        sampled_examples = []
        for e_id, (example, hyps) in enumerate(zip(examples, hypotheses)):
            for hyp_id, hyp in enumerate(hyps):
                try:
                    py_ast = asdl_ast_to_python_ast(hyp.tree, self.encoder.grammar)
                    code = astor.to_source(py_ast).strip()
                    tokenize_code(code)  # make sure the code is tokenizable!
                    sampled_example = Example(idx='%d-sample%d' % (example.idx, hyp_id),
                                              src_sent=example.src_sent,
                                              tgt_code=code,
                                              tgt_actions=hyp.action_infos,
                                              tgt_ast=hyp.tree)
                    sampled_examples.append(sampled_example)
                except:
                    print("Exception in converting tree to code:", file=sys.stdout)
                    print('-' * 60, file=sys.stdout)
                    traceback.print_exc(file=sys.stdout)
                    print('-' * 60, file=sys.stdout)

        sample_scores, enc_states = self.encoder.score(sampled_examples, return_enc_state=True)

        # compute baseline, which is an MLP
        # (sample_size) FIXME: reward is log-likelihood, shall we use activation here?
        b_x = self.b_x_l2(F.tanh(self.b_x_l1(enc_states.detach()))).view(-1)

        return sampled_examples, sample_scores, b_x

    def save(self, path):
        fname, ext = os.path.splitext(path)
        self.encoder.save(fname + '.encoder' + ext)
        self.decoder.save(fname + '.decoder' + ext)
        state_dict = {k: v for k, v in self.state_dict().iteritems() if not (k.startswith('decoder') or k.startswith('encoder'))}

        params = {
            'args': self.args,
            'state_dict': state_dict
        }

        torch.save(params, path)

    def load_parameters(self, path):
        fname, ext = os.path.splitext(path)
        encoder_states = torch.load(fname + '.encoder' + ext, map_location=lambda storage, loc: storage)['state_dict']
        self.encoder.load_state_dict(encoder_states)

        decoder_states = torch.load(fname + '.decoder' + ext, map_location=lambda storage, loc: storage)['state_dict']
        self.decoder.load_state_dict(decoder_states)

        vae_states = torch.load(path, map_location=lambda storage, loc: storage)['state_dict']
        self.load_state_dict(vae_states, strict=False)