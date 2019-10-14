# -*- coding: utf-8 -*-
"""DMSearchRanked.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1W7fHmAzRCdP8lo9gIcduEdMIH-a02JX-
"""

# from google.colab import drive
# drive.mount('/content/drive')

import nltk
nltk.download('stopwords')
nltk.download('wordnet')

from collections import defaultdict
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
from array import array
from tqdm import tqdm
import csv
import math
import re
import numpy as np
import os
from nltk.stem import WordNetLemmatizer


MY_DRIVE = '/content/drive/My Drive/Data Mining'

STYLE_WITH_DESC_N_TITLE = MY_DRIVE+'/styles_with_description_title_RandomSampled.csv'

INVERTED_IDX_FILE = MY_DRIVE+'/store_index_tf_idf_Random_lemmatized.dat'

COL_INDEX_ID = 0
COL_INDEX_DISPLAY_NAME = 9
COL_INDEX_DESC_TITLE = 13

class RankedIndexer():
  def __init__(self):
    self.index = defaultdict(list)  #the inverted index
    self.titleIndex = {}
    self.tf = defaultdict(list)   #term frequencies of terms in documents
                                                #documents in the same order as in the main index
    self.df = defaultdict(int)    #document frequencies of terms in the corpus
    self.numberOfDocs = 0

  def parseData(self):
    return

  def getTerms(self, doc):
    #print('Original\n'+doc)
    doc = doc.lower()
    #print('lowered\n\n'+doc)
    doc = re.sub(r'[^a-z0-9 ]',' ',doc) #put spaces instead of non-alphanumeric characters
    terms = doc.split()

    terms = [term for term in terms if term not in self.stopwords]
    terms = [self.lemmatizer.lemmatize(term) for term in terms]
    terms = [self.stemmer.stem(term) for term in terms]
    #print('Terms:\n\n')
    #print(terms)
    return terms

  def prepareParams(self):
    self.stopwords = set(stopwords.words('english'))
    self.dataFile = STYLE_WITH_DESC_N_TITLE
    self.indexFile = INVERTED_IDX_FILE
    self.stemmer = PorterStemmer()
    self.lemmatizer = WordNetLemmatizer()

  def writeIndexToFile(self):
    '''write the inverted index to the file'''
    file=open(self.indexFile, 'w')
    print(self.numberOfDocs, file = file)
    self.numberOfDocs = float(self.numberOfDocs)

    for term in self.index.keys():
        postingList=[]
        for posting in self.index[term]:
            docID=posting[0]
            positions=posting[1]
            postingList.append(':'.join([str(docID) ,','.join(map(str,positions))]))
        postingData = ';'.join(postingList)
        tfData = ','.join(map(str, self.tf[term]))
        idfData = '%4f'%(1+np.log(self.numberOfDocs / self.df[term]))

        print('|'.join((term, postingData, tfData, idfData)), end="\n", file = file)
    file.close()

  def createTfIdfIndex(self):
    self.prepareParams()

    with open(STYLE_WITH_DESC_N_TITLE, 'r', encoding='latin-1') as csvfile:
      reader = csv.reader(csvfile)

      for rowNo, row in enumerate(tqdm(reader)):
        if rowNo==0:
          continue
        docId = row[COL_INDEX_ID]
        terms = self.getTerms(row[COL_INDEX_DESC_TITLE])
        if terms == None:
          continue

        self.titleIndex[docId] = row[COL_INDEX_DISPLAY_NAME]
        self.numberOfDocs += 1

        termDict = {}
        for position, term in enumerate(terms):
          try:
            termDict[term][1].append(position)
          except:
            termDict[term]=[docId, array('I',[position])]

        # Normalize the doc
        norm = 0
        for term, posting in termDict.items():
          norm += len(posting)**2
          norm = math.sqrt(norm)

        #calculate tf and df weights
        for term, posting in termDict.items():
          self.tf[term].append('%.4f' % (len(posting[1])/norm))
          self.df[term] += 1

        for term, posting in termDict.items():
          self.index[term].append(posting)


        #print (row[COL_INDEX_DESC_TITLE])
        #print (row[COL_INDEX_ID])

      #if rowNo%1000==0:
      print(len(self.index))

      self.writeIndexToFile()
          #break
    #print(os.listdir('/content/drive/My Drive/Data Mining'))


if __name__ == '__main__':
  indexer = RankedIndexer()
  indexer.createTfIdfIndex()
