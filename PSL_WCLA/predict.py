# -*- coding: utf-8 -*-
#! /usr/bin/env python
#SELECT WHICH MODEL YOU WISH TO RUN:
#from cnn_lstm import CNN_LSTM   #OPTION 0
#from lstm_cnn import LSTM_CNN   #OPTION 1
#from cnn_lstm import CNN_LSTM   #OPTION 2
from cnn import CNN_LSTM   #OPTION 2

#istrain= False
istrain= True      
MODEL_TO_RUN = 0
from confusionmatrix import ConfusionMatrix
from metrics_mc import *
import tensorflow as tf
import numpy as np
import os
import time
import datetime
import batchgen
from keras.utils import np_utils

# Parameters
# ==================================================
# Model Hyperparameters
num_classes  = 10     #128
seq_legth = 1000 
embedding_dim = 20
num_hidden = 128
filter_sizes = [1,3,5,9,15,21]  #3
num_filters = 20
dropout_prob = 0.5 #0.5
learning_rate = 0.0005
l2_reg_lambda = 0.0

# Training parameters
batch_size = 100
num_epochs = 100 #200
evaluate_every = 20 #100
checkpoint_every = 10000 #100
num_checkpoints = 1 #Checkpoints to store

# Data Preparation
import h5py
#f=h5py.File('../data/BLOSUM.hdf5','r')
#x_train=f['x_train']
#x_test=f['x_test']
#y_train=f['y_train']
#y_test=f['y_test']
#y_train = np.array(y_train)
#x_train = np.array(x_train)
#y_test = np.array(y_test)
#x_test = np.array(x_test)
f=h5py.File('./data/deeploc.hdf5','r')
x=f["x"]
y=f["y"]
mask=f["mask"]
x=np.array(x)
y=np.array(y)
num=x.shape[0]
indices = np.arange(num)
np.random.seed(seed=123456)
np.random.shuffle(indices)
x = x[indices]
y = y[indices]
#y=np_utils.to_categorical(y)  
test_index=[]
train_index = []
for i in range(num):
    if i%4 == 0:
        test_index.append(i)
    else :
        train_index.append(i)

x_test=x[test_index,:,:]
x_train=x[train_index,:,:]
y_test=y[test_index]
y_train=y[train_index]


indices = np.arange(x_train.shape[0])
np.random.shuffle(indices)
x_train = x_train[indices]
y_train = y_train[indices]
print(x_train.shape)
print(y_train.shape)
print(x_test.shape)
print(y_test.shape)
#embed()


# Training
# ==================================================
with tf.Graph().as_default():
    session_conf = tf.ConfigProto(allow_soft_placement=True, log_device_placement=False)
    sess = tf.Session(config=session_conf)
    with sess.as_default():
        #embed()
        if (MODEL_TO_RUN == 0):
            model = CNN_LSTM(seq_legth,num_classes,embedding_dim,filter_sizes,num_filters,num_hidden)
        elif (MODEL_TO_RUN == 1):
            model = LSTM_CNN(seq_legth,num_classes,embedding_dim,filter_sizes,num_filters,num_hidden)
#        elif (MODEL_TO_RUN == 2):
#            model = CNN(x_train.shape[1],y_train.shape[1],len(vocab_processor.vocabulary_),
#                        embedding_dim,filter_sizes,num_filters,l2_reg_lambda)
#        elif (MODEL_TO_RUN == 3):
#            model = LSTM(x_train.shape[1],y_train.shape[1],len(vocab_processor.vocabulary_),embedding_dim)
        else:
            print ("PLEASE CHOOSE A VALID MODEL!\n0 = CNN_LSTM\n1 = LSTM_CNN\n2 = CNN\n3 = LSTM\n")
            exit();

        # Define Training procedure
        global_step = tf.Variable(0, name="global_step", trainable=False)
        #learning_rate = tf.train.exponential_decay(0.002,global_step,100,0.96,staircase=True)
        optimizer = tf.train.AdamOptimizer(learning_rate)
        grads_and_vars = optimizer.compute_gradients(model.loss)
        train_op = optimizer.apply_gradients(grads_and_vars, global_step=global_step)
        
        
        # Keep track of gradient values and sparsity (optional)
        grad_summaries = []
        for g, v in grads_and_vars:
            if g is not None:
                grad_hist_summary = tf.summary.histogram("{}/grad/hist".format(v.name), g)
                sparsity_summary = tf.summary.scalar("{}/grad/sparsity".format(v.name), tf.nn.zero_fraction(g))
                grad_summaries.append(grad_hist_summary)
                grad_summaries.append(sparsity_summary)
        grad_summaries_merged = tf.summary.merge(grad_summaries)
        # Output directory for models and summaries
        timestamp = str(int(time.time()))
        out_dir = os.path.abspath(os.path.join(os.path.curdir, "predict", timestamp))
        print("Writing to {}\n".format(out_dir))
        # Summaries for loss and accuracy
        loss_summary = tf.summary.scalar("loss", model.loss)
        acc_summary = tf.summary.scalar("accuracy", model.accuracy)
        # Train Summaries
        train_summary_op = tf.summary.merge([loss_summary, acc_summary, grad_summaries_merged])
        train_summary_dir = os.path.join(out_dir, "summaries", "train")
        train_summary_writer = tf.summary.FileWriter(train_summary_dir, sess.graph)
        # Dev summaries
        dev_summary_op = tf.summary.merge([loss_summary, acc_summary])
        dev_summary_dir = os.path.join(out_dir, "summaries", "dev")
        dev_summary_writer = tf.summary.FileWriter(dev_summary_dir, sess.graph)
        
        
        # Checkpoint directory. Tensorflow assumes this directory already exists so we need to create it
        checkpoint_dir = os.path.abspath(os.path.join("predict", "checkpoints"))
        checkpoint_prefix = os.path.join(checkpoint_dir, "model.ckpt")
        if not os.path.exists(checkpoint_dir):
            os.makedirs(checkpoint_dir)
        saver = tf.train.Saver(tf.global_variables(), max_to_keep=num_checkpoints)

        # Initialize all variables
        sess.run(tf.global_variables_initializer())
        #training = tf.placeholder(tf.bool)
        #TRAINING STEP
        def train_step(x_batch, y_batch,save=True):
            feed_dict = {model.input_x: x_batch, model.input_y: y_batch, model.dropout_keep_prob: dropout_prob,model.training: True}
            _, step, summaries, loss, predictions,semantic = sess.run([train_op, global_step, train_summary_op, model.loss, model.score,model.semantic],feed_dict)
            time_str = datetime.datetime.now().isoformat()
            current_step = tf.train.global_step(sess, global_step)
            if current_step % 50 == 0:
                print("{}: step {}, loss {:g}, acc {:g}".format(time_str, step, loss, accuracy))
            if save:
                train_summary_writer.add_summary(summaries, step)
            return predictions,semantic

        #EVALUATE MODEL
        def dev_step(x_batch, y_batch,writer=None,save=True):
            feed_dict = {model.input_x: x_batch, model.input_y: y_batch, model.dropout_keep_prob: 1,model.training: False}
            step, predictions,summaries, loss, accuracy,semantic = sess.run([global_step,model.score, dev_summary_op, model.loss, model.accuracy,model.semantic], feed_dict)
            #step,predictions,loss, accuracy = sess.run([global_step,model.scores, model.loss,model.accuracy], feed_dict)            
            time_str = datetime.datetime.now().isoformat()
            print("{}: step {}, loss {:g}, acc {:g}".format(time_str, step, loss, accuracy))
            if save:
                if writer:
                    writer.add_summary(summaries, step)
            return accuracy ,predictions,semantic
        #CREATE THE BATCHES GENERATOR
        batches = batchgen.gen_batch(list(zip(x_train, np_utils.to_categorical(y_train))), batch_size, num_epochs)
        #TRAIN FOR EACH BATCH
        max_acc=0
        if istrain:
            for i,batch in enumerate(batches):
                x_batch, y_batch = zip(*batch)
                predictions ,semantic= train_step(x_batch, y_batch)
                current_step = tf.train.global_step(sess, global_step)
                if current_step % evaluate_every == 0:
                    print("\nEvaluation:")
                    accuracy,predictions,semantic = dev_step(x_test, y_test,writer=dev_summary_writer)
                    if accuracy>max_acc:
                        max_acc=accuracy
                        path = saver.save(sess, checkpoint_prefix, global_step=current_step)
                        print("Saved model checkpoint to {}\n".format(path))
        else:
            ckpt = tf.train.get_checkpoint_state(checkpoint_dir)  
            saver.restore(sess,ckpt.model_checkpoint_path)     
            accuracy,X_test = dev_step(x_test, np_utils.to_categorical(y_test))
            for i,batch in enumerate(batches):
                x_batch, y_batch = zip(*batch)
                predictions = train_step(x_batch, y_batch)
                if i==0:
                    X_train=predictions
                else:
                    print(i)
                    X_train=np.concatenate((X_train,predictions))
        #dev_step(x_dev, y_dev, writer=dev_summary_writer)
#print(X_train.shape)
#print(y_train.shape)
#print(X_test.shape)
#print(y_test.shape)
#import h5py
#f=h5py.File('data/predict.hdf5')
##spec_dtype = h5py.special_dtype(vlen=np.dtype('float32'))
#d1=f.create_dataset('x_train',data=X_train)
#d2=f.create_dataset('x_test',data=X_test)
#d3=f.create_dataset('y_train',data=y_train)
#d4=f.create_dataset('y_test',data=y_test)






