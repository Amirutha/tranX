#!/bin/bash
set -e

#source activate py3torch3cuda9

seed=${1:-0}
version=${2:-0}
vocab="data/libro/vocab.freq2.bin"
train_file="data/libro/train.bin"
dev_file="data/libro/dev.bin"
test_file="data/libro/test.bin"
dropout=0.5
hidden_size=256
embed_size=128
action_embed_size=128
field_embed_size=32
type_embed_size=32
lr_decay=0.985
lr_decay_after_epoch=20
max_epoch=200
patience=10   # disable patience since we don't have dev set
beam_size=5
batch_size=10
lr=0.0025
ls=0.1
lstm='lstm'
model_name=model.libro.sup.${lstm}.hid${hidden_size}.embed${embed_size}.act${action_embed_size}.field${field_embed_size}.type${type_embed_size}.drop${dropout}.lr_decay${lr_decay}.lr_dec_aft${lr_decay_after_epoch}.beam${beam_size}.$(basename ${vocab}).$(basename ${train_file}).pat${patience}.max_ep${max_epoch}.batch${batch_size}.lr${lr}.glorot.no_par_info.no_copy.ls${ls}.seed${seed}.version${version}

python -u exp.py \
    --seed ${seed} \
    --mode train \
    --batch_size ${batch_size} \
    --asdl_file asdl/lang/lisp/lisp_asdl.txt \
    --transition_system lisp \
    --train_file ${train_file} \
    --dev_file ${dev_file}\
    --test_file ${test_file}\
    --vocab ${vocab} \
    --lstm ${lstm} \
    --primitive_token_label_smoothing ${ls} \
    --no_parent_field_type_embed \
    --no_parent_production_embed \
    --no_parent_field_embed \
    --no_parent_state \
    --hidden_size ${hidden_size} \
    --embed_size ${embed_size} \
    --action_embed_size ${action_embed_size} \
    --field_embed_size ${field_embed_size} \
    --type_embed_size ${type_embed_size} \
    --dropout ${dropout} \
    --patience ${patience} \
    --max_epoch ${max_epoch} \
    --lr ${lr} \
    --no_copy \
    --lr_decay ${lr_decay} \
    --lr_decay_after_epoch ${lr_decay_after_epoch} \
    --decay_lr_every_epoch \
    --glorot_init \
    --beam_size ${beam_size} \
    --decode_max_time_step 55 \
    --log_every 50 \
    --save_all_models \
    --save_to saved_models/libro/${model_name} 2>logs/libro/${model_name}.log

cp saved_models/libro/${model_name}.bin data/pretrained_models/libro-${version}
. scripts/libro/test.sh saved_models/libro/${model_name}.bin 2>>logs/libro/${model_name}.log

