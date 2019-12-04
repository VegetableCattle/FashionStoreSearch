# -*- coding: utf-8 -*-
"""CaptionEvaluator.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/11dOehAqpD3RUpdFQqrxixQBFz4KTKk1O
"""

# Import TensorFlow and enable eager execution
# This code requires TensorFlow version >=1.9
import tensorflow as tf
tf.enable_eager_execution()

# We'll generate plots of attention in order to see which parts of an image
# our model focuses on during captioning
import matplotlib.pyplot as plt

# Scikit-learn includes many helpful utilities
from sklearn.model_selection import train_test_split
from sklearn.utils import shuffle

import re
import numpy as np
import os
import time
import json
from glob import glob
from PIL import Image
import pickle

file_path = os.path.dirname(os.path.realpath(__file__))

MODEL_FILE_PATH = file_path + '/model_data/'

max_length = 0
attention_features_shape = 0
embedding_dim = 0
units = 0
vocab_size = 0
tokenizer = None
meta_dict = None
encoder = None
decoder = None
image_features_extract_model = None


def prepare_params():

    global max_length
    global attention_features_shape
    global embedding_dim
    global units
    global vocab_size
    global tokenizer
    global meta_dict
    global encoder
    global decoder
    global image_features_extract_model

    with open(MODEL_FILE_PATH+'tokenizer.gru.pickle', 'rb') as handle:
        tokenizer = pickle.load(handle)

    with open(MODEL_FILE_PATH+'meta.gru.pickle', 'rb') as handle:
        meta_dict = pickle.load(handle)

    max_length = meta_dict['max_length']
    print(max_length)

    attention_features_shape = meta_dict['attention_features_shape']
    print(attention_features_shape)

    embedding_dim = meta_dict['embedding_dim']
    print(embedding_dim)

    units = meta_dict['units']
    print(units)

    vocab_size = meta_dict['vocab_size']
    print(vocab_size)
    encoder = CNN_Encoder(embedding_dim)
    decoder = RNN_Decoder(embedding_dim, units, vocab_size)

    image_model = tf.keras.applications.InceptionV3(include_top=False,
                                                    weights='imagenet')


    new_input = image_model.input
    hidden_layer = image_model.layers[-1].output
    image_features_extract_model = tf.keras.Model(new_input, hidden_layer)

    encoder.load_weights(MODEL_FILE_PATH+'encoder.gru')
    decoder.load_weights(MODEL_FILE_PATH+'decoder.gru')
    decoder.attention.load_weights(MODEL_FILE_PATH+'attention.gru')
    print('Caption generator params loaded')

def gru(units):
  # If you have a GPU, we recommend using the CuDNNGRU layer (it provides a
  # significant speedup).
  if tf.test.is_gpu_available():
    return tf.keras.layers.CuDNNGRU(units,
                                    return_sequences=True,
                                    return_state=True,
                                    recurrent_initializer='glorot_uniform')
  else:
    return tf.keras.layers.GRU(units,
                               return_sequences=True,
                               return_state=True,
                               recurrent_activation='sigmoid',
                               recurrent_initializer='glorot_uniform')

class BahdanauAttention(tf.keras.Model):
  def __init__(self, units):
    super(BahdanauAttention, self).__init__()
    self.W1 = tf.keras.layers.Dense(units)
    self.W2 = tf.keras.layers.Dense(units)
    self.V = tf.keras.layers.Dense(1)

  def call(self, features, hidden):
    # features(CNN_encoder output) shape == (batch_size, 64, embedding_dim)

    # hidden shape == (batch_size, hidden_size)
    # hidden_with_time_axis shape == (batch_size, 1, hidden_size)
    hidden_with_time_axis = tf.expand_dims(hidden, 1)

    # score shape == (batch_size, 64, hidden_size)
    score = tf.nn.tanh(self.W1(features) + self.W2(hidden_with_time_axis))

    # attention_weights shape == (batch_size, 64, 1)
    # we get 1 at the last axis because we are applying score to self.V
    attention_weights = tf.nn.softmax(self.V(score), axis=1)

    # context_vector shape after sum == (batch_size, hidden_size)
    context_vector = attention_weights * features
    context_vector = tf.reduce_sum(context_vector, axis=1)

    return context_vector, attention_weights

class CNN_Encoder(tf.keras.Model):
    # Since we have already extracted the features and dumped it using pickle
    # This encoder passes those features through a Fully connected layer
    def __init__(self, embedding_dim):
        super(CNN_Encoder, self).__init__()
        # shape after fc == (batch_size, 64, embedding_dim)
        self.fc = tf.keras.layers.Dense(embedding_dim)

    def call(self, x):
        x = self.fc(x)
        x = tf.nn.relu(x)
        return x

class RNN_Decoder(tf.keras.Model):
  def __init__(self, embedding_dim, units, vocab_size):
    super(RNN_Decoder, self).__init__()
    self.units = units

    self.embedding = tf.keras.layers.Embedding(vocab_size, embedding_dim)
    self.gru = gru(self.units)
    self.fc1 = tf.keras.layers.Dense(self.units)
    self.fc2 = tf.keras.layers.Dense(vocab_size)

    self.attention = BahdanauAttention(self.units)

  def call(self, x, features, hidden):
    # defining attention as a separate model
    context_vector, attention_weights = self.attention(features, hidden)

    # x shape after passing through embedding == (batch_size, 1, embedding_dim)
    x = self.embedding(x)

    # x shape after concatenation == (batch_size, 1, embedding_dim + hidden_size)
    x = tf.concat([tf.expand_dims(context_vector, 1), x], axis=-1)

    # passing the concatenated vector to the GRU
    output, state = self.gru(x)

    # shape == (batch_size, max_length, hidden_size)
    x = self.fc1(output)

    # x shape == (batch_size * max_length, hidden_size)
    x = tf.reshape(x, (-1, x.shape[2]))

    # output shape == (batch_size * max_length, vocab)
    x = self.fc2(x)

    return x, state, attention_weights

  def reset_state(self, batch_size):
    return tf.zeros((batch_size, self.units))


def load_image(image_path):
    # print(image_path)
    print('Loading image from : ' + image_path)
    img = tf.read_file(image_path)
    print('Decoding image from : ' + image_path)
    img = tf.image.decode_jpeg(img, channels=3)
    print('Resizing image from : ' + image_path)
    img = tf.image.resize_images(img, (299, 299))
    print('Preprocessing image from : ' + image_path)
    img = tf.keras.applications.inception_v3.preprocess_input(img)
    print('Preprocessing Done')
    return img, image_path


def evaluate(image):
    print('Generating caption in evaluate function')
    attention_plot = np.zeros((max_length, attention_features_shape))
    print('Generating caption in evaluate function2')
    hidden = decoder.reset_state(batch_size=1)
    print('Generating caption in evaluate function3')
    temp_input = tf.expand_dims(load_image(image)[0], 0)
    print('Generating caption in evaluate function4')
    img_tensor_val = image_features_extract_model(temp_input)
    print('Generating caption in evaluate function5')
    img_tensor_val = tf.reshape(img_tensor_val, (img_tensor_val.shape[0], -1, img_tensor_val.shape[3]))

    features = encoder(img_tensor_val)

    # print(features)

    dec_input = tf.expand_dims([tokenizer.word_index['<start>']], 0)
    result = []
    # print(dec_input)

    # print(decoder.attention.W1)
    print('Entering caption generation loop')
    for i in range(max_length):
        predictions, hidden, attention_weights = decoder(dec_input, features, hidden)
        # print(predictions)
        attention_plot[i] = tf.reshape(attention_weights, (-1, )).numpy()

        predicted_id = tf.argmax(predictions[0]).numpy()
        result.append(tokenizer.index_word[predicted_id])

        if tokenizer.index_word[predicted_id] == '<end>':
            return result, attention_plot

        dec_input = tf.expand_dims([predicted_id], 0)

    attention_plot = attention_plot[:len(result), :]
    return result, attention_plot

def plot_attention(image, result, attention_plot):
    temp_image = np.array(Image.open(image))

    fig = plt.figure(figsize=(10, 10))

    len_result = len(result)
    for l in range(len_result):
        temp_att = np.resize(attention_plot[l], (8, 8))
        ax = fig.add_subplot(len_result//2, len_result//2, l+1)
        ax.set_title(result[l])
        img = ax.imshow(temp_image)
        ax.imshow(temp_att, cmap='gray', alpha=0.6, extent=img.get_extent())

    plt.tight_layout()
    plt.show()

# https://s3-ap-southeast-2.amazonaws.com/piano.revolutionise.com.au/gallery/i7yq0ctwmdcftxbm.jpg

# image_url = 'https://tensorflow.org/images/surf.jpg'
# # image_url = 'https://s3-ap-southeast-2.amazonaws.com/piano.revolutionise.com.au/gallery/i7yq0ctwmdcftxbm.jpg'
# # image_url = '/content/4576671.jpg'
# # image_url = '/content/65567.jpg'
# image_extension = image_url[-4:]
# image_path = tf.keras.utils.get_file('image3'+image_extension,
#                                      origin=image_url)
# print(image_path)
# result, attention_plot = evaluate(image_path)
# print ('Prediction Caption:', ' '.join(result))
# plot_attention(image_path, result, attention_plot)

# # opening the image
# Image.open(image_path)


#######################################Caption generation for all images####################

#from google.colab import drive
#drive.mount('/content/drive', force_remount=False)

#DIBA_DRIVE = '/content/drive/My Drive/Rubel/DM/img_captioning/'

#FLICKR_IMG_ZIP = DIBA_DRIVE + 'flickr-image-dataset.zip'
#FLICKR_FILE = DIBA_DRIVE + 'captions_sampled.csv'

#FILE_PATH = '/content/flickr_img/'

# import csv
# from tqdm import tqdm
# FLICKR_FILE_GEN = DIBA_DRIVE+'captions_sampled_generated_gru.csv'
# FILE_IN_PATH = '/content/flickr_img/flickr30k_images/flickr30k_images/'
# FLICKR_FILE = DIBA_DRIVE+'captions_sampled.csv'

# with open(FLICKR_FILE,'r', encoding="latin-1") as csvinput:
#         with open(FLICKR_FILE_GEN, 'w', newline='', encoding="latin-1") as csvoutput:
#             writer = csv.writer(csvoutput, lineterminator='\n')
#             reader = csv.reader(csvinput)

#             all = []
#             row = next(reader)
#             print(row)
#             row.append('Caption')
#             writer.writerow(row)
#     #        print(row)
#            # all.append(row)

#             for i, row in enumerate(tqdm(reader)):
#               image_path = FILE_IN_PATH+row[0]
#               # print(image_path)
#               result, _ = evaluate2(image_path)

#               caption = ' '.join(result)
#               if len(result) == max_length:
#                 print('error?')
#                 print(caption)

#               if i%100 == 0:
#                 print(caption)
#                 #print(fileName)
#                 #print(description)
#               row.append(caption)
#     #             all.append(row)
#     #             if i>0 && i%100==0:
#               writer.writerow(row)