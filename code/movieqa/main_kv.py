#!/usr/bin/python

import argparse
import os
import numpy as np
import random
import tensorflow as tf
import tqdm

from dataset_reader import DatasetReader
from model_kv import KeyValueMemNN

flags = tf.app.flags
flags.DEFINE_float("learning_rate", 0.01, "Learning rate for Adam Optimizer.")
flags.DEFINE_float("epsilon", 1e-8, "Epsilon value for Adam Optimizer.")
flags.DEFINE_float("max_grad_norm", 40.0, "Clip gradients to this norm.")
flags.DEFINE_integer("evaluation_interval", 10, "Evaluate and print results every x epochs")
flags.DEFINE_integer("batch_size", 16, "Batch size for training.")
flags.DEFINE_integer("hops", 3, "Number of hops in the Memory Network.")
flags.DEFINE_integer("epochs", 3, "Number of epochs to train for.")
flags.DEFINE_integer("embedding_size", 100, "Embedding size for embedding matrices.")
flags.DEFINE_string("checkpoint_dir", "checkpoints", "checkpoint directory [checkpoints]")


FLAGS = flags.FLAGS
QUESTION = "question"
QN_ENTITIES = "qn_entities"
ANS_ENTITIES = "ans_entities"
SOURCES = "sources"
RELATIONS = "relations"
TARGETS = "targets"
ANSWER = "answer"
KEYS = "keys"
VALUES = "values"

maxlen = {}


def set_maxlen(train_maxlen, test_maxlen, dev_maxlen):
  global maxlen
  qn_max_len = max(train_maxlen[QUESTION], test_maxlen[QUESTION], dev_maxlen[QUESTION])
  qn_entities_max_len = max(train_maxlen[QN_ENTITIES], test_maxlen[QN_ENTITIES], dev_maxlen[QN_ENTITIES])
  ans_entities_max_len = max(train_maxlen[ANS_ENTITIES], test_maxlen[ANS_ENTITIES], dev_maxlen[ANS_ENTITIES])
  sources_max_len = max(train_maxlen[SOURCES], test_maxlen[SOURCES], dev_maxlen[SOURCES])
  maxlen[QUESTION], maxlen[QN_ENTITIES], maxlen[ANS_ENTITIES] = qn_max_len, qn_entities_max_len, ans_entities_max_len
  maxlen[SOURCES], maxlen[RELATIONS], maxlen[TARGETS] = sources_max_len, sources_max_len, sources_max_len
  maxlen[KEYS] = maxlen[SOURCES]
  maxlen[VALUES] = maxlen[SOURCES]


def prepare_batch(batch_examples):
  batch_size = FLAGS.batch_size
  batch_dict = {}
  batch_dict[QUESTION] = gather_single_column_from_batch(batch_examples, QUESTION)
  batch_dict[QN_ENTITIES] = gather_single_column_from_batch(batch_examples, QN_ENTITIES)
  batch_dict[SOURCES] = gather_single_column_from_batch(batch_examples, SOURCES)
  batch_dict[RELATIONS] = gather_single_column_from_batch(batch_examples, RELATIONS)
  batch_dict[TARGETS] = gather_single_column_from_batch(batch_examples, TARGETS)

  batch_dict[KEYS] = gather_key_from_batch(batch_examples)
  batch_dict[VALUES] = gather_single_column_from_batch(batch_examples, TARGETS)
  print batch_dict[QUESTION]

  labels = np.zeros([batch_size])
  for i in xrange(batch_size):
    labels[i] = random.sample(batch_examples[i][ANS_ENTITIES], 1)[0]
  batch_dict[ANSWER] = labels
  return batch_dict


def gather_single_column_from_batch(batch_examples, column_name):
  batch_size = FLAGS.batch_size
  column = []
  for i in xrange(batch_size):
    column.append(batch_examples[i][column_name])
  return np.array(column) #batch_size * maxlen(column_name)

def gather_key_from_batch(batch_examples):
  batch_size = FLAGS.batch_size
  column = []
  for i in xrange(batch_size):
    assert(len(batch_examples[i][SOURCES] == len(batch_examples[i][RELATIONS])))
    memory_length = len(batch_examples[i][SOURCES])
    memories = []
    src = batch_examples[i][SOURCES]
    rel = batch_examples[i][RELATIONS]
    for memory_index in xrange(memory_length):
      memories.append(np.array([src[memory_index], rel[memory_index]]))
    column.append(np.array(memories))
  return np.array(column) #batch_size * memory_length * 2

# def get_sparse_matrix(batch_examples, input_field_name):
#   batch_size = FLAGS.batch_size
#   indices = []
#   values = []
#   shape = [batch_size, maxlen[input_field_name]]
#   for row in xrange(batch_size):
#     input_field = batch_examples[row][input_field_name]
#     for col in input_field:
#       indices.append([row, col])
#       values.append(1)
#   return [indices, values, shape]
#
# def get_sparse_matrix_for_keys(batch_examples):
#   batch_size = FLAGS.batch_size
#   key_indices = []
#   key_values = []
#   key_shape = [batch_size, maxlen[SOURCES] + maxlen[RELATIONS]]
#   for row in xrange(batch_size):
#     sources_list = batch_examples[row][SOURCES]
#     relations_list = batch_examples[row][RELATIONS]
#     for col in sources_list:
#       key_indices.append([row, col])
#       key_values.append(1)
#     for col in relations_list:
#       key_indices.append([row, col])
#       key_values.append(1)
#   return [key_indices, key_values, key_shape]


def main(args):
  if not os.path.exists(FLAGS.checkpoint_dir):
    os.makedirs(FLAGS.checkpoint_dir)
  args.input_examples = args.train_examples
  train_reader = DatasetReader(args, share_idx=True)
  train_examples = train_reader.get_examples()
  args.input_examples = args.test_examples
  test_reader = DatasetReader(args, share_idx=True)
  test_examples = test_reader.get_examples()
  args.input_examples = args.dev_examples
  dev_reader = DatasetReader(args, share_idx=True)
  dev_examples = dev_reader.get_examples()
  set_maxlen(train_reader.get_max_lengths(), test_reader.get_max_lengths(), dev_reader.get_max_lengths())

  batch_size = FLAGS.batch_size
  num_train = len(train_examples)
  batches = zip(range(0, num_train - batch_size, batch_size), range(batch_size, num_train, batch_size))
  batches = [(start, end) for start, end in batches]
  batches = batches[0:1]
  print batches

  with tf.Session() as sess:
    model = KeyValueMemNN(sess, maxlen, train_reader.get_idx_size(), train_reader.get_entity_idx_size())
    for epoch in range(1, FLAGS.epochs+1):
      np.random.shuffle(batches)
      total_cost = 0.0
      for start, end in batches:
        batch_examples = train_examples[start:end]
        batch_dict = prepare_batch(batch_examples)
        cost_t = model.batch_fit(batch_dict)
        print cost_t, "..."
        total_cost += cost_t
      print total_cost

if __name__ == "__main__":
  parser = argparse.ArgumentParser(description='Specify arguments')
  parser.add_argument('--train_examples', help='the train file', required=True)
  parser.add_argument('--test_examples', help='the test file', required=True)
  parser.add_argument('--dev_examples', help='the dev file', required=True)
  parser.add_argument('--word_idx', help='word vocabulary', required=True)
  parser.add_argument('--entity_idx', help='entity vocabulary', required=True)
  parser.add_argument('--relation_idx', help='relation vocabulary', required=True)
  parser.add_argument('--idx', help='overall vocabulary', required=True)
  args = parser.parse_args()
  main(args)