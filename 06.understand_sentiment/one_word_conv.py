# Copyright (c) 2018 PaddlePaddle Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import print_function

import os
import paddle
import paddle.fluid as fluid
from functools import partial
import numpy as np
import one_word

CLASS_DIM = 2
EMB_DIM = 128
HID_DIM = 512
BATCH_SIZE = 32

ALL_DATA = '/work/book/06.understand_sentiment/one_word_reviews.json'
TRAIN_FILE = '/work/book/06.understand_sentiment/one_word_reviews_train.json'
TEST_FILE = '/work/book/06.understand_sentiment/one_word_reviews_test.json'


def convolution_net(data, input_dim, class_dim, emb_dim, hid_dim):
    emb = fluid.layers.embedding(
        input=data, size=[input_dim, emb_dim], is_sparse=False)
    # print(fluid.executor.as_numpy(emb))
    # print(emb)
    conv_3 = fluid.nets.sequence_conv_pool(
        input=emb,
        num_filters=hid_dim,
        filter_size=3,
        act="tanh",
        pool_type="sqrt")
    conv_4 = fluid.nets.sequence_conv_pool(
        input=emb,
        num_filters=hid_dim,
        filter_size=4,
        act="tanh",
        pool_type="sqrt")
    prediction = fluid.layers.fc(
        input=[conv_3, conv_4], size=class_dim, act="softmax")
    return prediction


def inference_program(word_dict):
    data = fluid.layers.data(
        name="words", shape=[1], dtype="int64", lod_level=1)

    dict_dim = len(word_dict)
    net = convolution_net(data, dict_dim, CLASS_DIM, EMB_DIM, HID_DIM)
    return net


def train_program(word_dict):
    prediction = inference_program(word_dict)
    label = fluid.layers.data(name="label", shape=[1], dtype="int64")
    cost = fluid.layers.cross_entropy(input=prediction, label=label)
    avg_cost = fluid.layers.mean(cost)
    accuracy = fluid.layers.accuracy(input=prediction, label=label)
    return [avg_cost, accuracy]


def optimizer_func():
    return fluid.optimizer.Adagrad(learning_rate=0.002)


def train(use_cuda, train_program, params_dirname):
    place = fluid.CUDAPlace(0) if use_cuda else fluid.CPUPlace()
    print("Loading OneWord word dict....")
    word_dict = one_word.word_dict(ALL_DATA)

    print("Reading training data....")
    train_reader = paddle.batch(
        paddle.reader.shuffle(
            one_word.train(word_dict, TRAIN_FILE), buf_size=25000),
        batch_size=BATCH_SIZE)

    print("Reading testing data....")
    test_reader = paddle.batch(
        one_word.test(word_dict, TEST_FILE), batch_size=BATCH_SIZE)

    trainer = fluid.Trainer(
        train_func=partial(train_program, word_dict),
        place=place,
        optimizer_func=optimizer_func)

    feed_order = ['words', 'label']

    def event_handler(event):
        if isinstance(event, fluid.EndStepEvent):
            if event.step % 10 == 0:
                avg_cost, acc = trainer.test(
                    reader=test_reader, feed_order=feed_order)

                print('Step {0}, Test Loss {1:0.2}, Acc {2:0.2}'.format(
                    event.step, avg_cost, acc))

                print("Step {0}, Epoch {1} Metrics {2}".format(
                    event.step, event.epoch, map(np.array, event.metrics)))

        elif isinstance(event, fluid.EndEpochEvent):
            trainer.save_params(params_dirname)

    trainer.train(
        num_epochs=1,
        event_handler=event_handler,
        reader=train_reader,
        feed_order=feed_order)


def infer(use_cuda, inference_program, params_dirname=None):
    place = fluid.CUDAPlace(0) if use_cuda else fluid.CPUPlace()
    word_dict = one_word.word_dict(ALL_DATA)

    inferencer = fluid.Inferencer(
        infer_func=partial(inference_program, word_dict),
        param_path=params_dirname,
        place=place)

    # Setup input by creating LoDTensor to represent sequence of words.
    # Here each word is the basic element of the LoDTensor and the shape of 
    # each word (base_shape) should be [1] since it is simply an index to 
    # look up for the corresponding word vector.
    # Suppose the length_based level of detail (lod) info is set to [[3, 4, 2]],
    # which has only one lod level. Then the created LoDTensor will have only 
    # one higher level structure (sequence of words, or sentence) than the basic 
    # element (word). Hence the LoDTensor will hold data for three sentences of 
    # length 3, 4 and 2, respectively. 
    # Note that lod info should be a list of lists.

    reviews_str = [
        'angel', 'assure', 'brave', 'clear', 'convience', 'desiring', 'ease',
        'enjoy'
        'fast', 'healthy', 'grief', 'haste', 'incense', 'lack', 'mad', 'odor',
        'pig', 'rash', 'rip', 'shame'
    ]

    reviews = [c.split() for c in reviews_str]

    UNK = word_dict['<unk>']
    lod = []
    for c in reviews:
        lod.append([word_dict.get(words, UNK) for words in c])

    base_shape = [[len(c) for c in lod]]

    tensor_words = fluid.create_lod_tensor(lod, base_shape, place)
    results = inferencer.infer({'words': tensor_words})

    for i, r in enumerate(results[0]):
        print(reviews_str[i], " positive: ", r[0], "negative: ", r[1])
        # print("Predict probability of ", r[0], " to be positive and ", r[1],
        #      " to be negative for review \'", reviews_str[i], "\'")


def main(use_cuda):
    if use_cuda and not fluid.core.is_compiled_with_cuda():
        return
    params_dirname = "oneword_understand_sentiment_conv.inference.model"
    train(use_cuda, train_program, params_dirname)
    infer(use_cuda, inference_program, params_dirname)


if __name__ == '__main__':
    use_cuda = False  # set to True if training with GPU
    main(use_cuda)
