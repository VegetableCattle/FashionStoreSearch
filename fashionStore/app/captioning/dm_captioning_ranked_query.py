# -*- coding: utf-8 -*-
"""DMRankedQUery.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1w34KO52kEZDAb2e_Mtvtl9y236auHA6s
"""

#from google.colab import drive
#drive.mount('/content/drive')

import nltk
# nltk.download('stopwords')
# nltk.download('wordnet')

from collections import defaultdict
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
from nltk.stem.snowball import SnowballStemmer
from array import array
#from tqdm import tqdm
import csv
#from tqdm import tqdm
import copy
import re
import os
from functools import reduce
from enum import Enum
import datetime
from numpy import dot
from numpy.linalg import norm
from captioning_doc_retriever import CaptionDocRetriever
from nltk.stem import WordNetLemmatizer


##############################
forCaptioning = True
##############################

file_path = os.path.dirname(os.path.realpath(__file__))

MY_DRIVE = file_path #os.getcwd() + '/app/captioning' #+ '/app' #'/content/drive/My Drive/Data Mining'

DIBA_DRIVE = file_path #os.getcwd() + '/app/captioning'#+ '/app' #'/content/drive/My Drive/Rubel/DM/img_captioning'
MY_DRIVE = DIBA_DRIVE

FLICKR_FILE_GEN = DIBA_DRIVE+'/captions_sampled_generated.csv'

FLICKR_INVERTED_IDX_FILE = DIBA_DRIVE+'/flickr_index_tf_idf_Random.dat'

COL_INDEX_ID = 0
COL_INDEX_DISPLAY_NAME = 9
COL_INDEX_DESC_TITLE = 13

COL_FLICKR_CAPTION = 3




MAX_NO_RESULT = 20

class QueryType(Enum):
  OWQ = 1
  FTQ = 2
  PhQ = 3

class ImageQueryHandler():
  def __init__(self):
    self.index={}
    self.index={}
    self.titleIndex={}
    self.tf={}     #term frequencies
    self.idf={}    #inverse document frequencies

  def readIndex(self):
    file=open(self.indexFile, 'r')
    self.numberOfDocs = int(file.readline().rstrip())

    for line in (file):
      line=line.rstrip()
      term, postings, tfl, idf = line.split('|')    #term='termID', postings='docID1:pos1,pos2;docID2:pos1,pos2'
      postings=postings.split(';')        #postings=['docId1:pos1,pos2','docID2:pos1,pos2']
      postings=[x.split(':') for x in postings] #postings=[['docId1', 'pos1,pos2'], ['docID2', 'pos1,pos2']]
      postings=[ [int(x[0][:-4]), map(int, x[1].split(','))] for x in postings ]   #final postings list
      self.index[term]=postings
      if term == 'differ':
          print(line)
      #read tf
      tfl = tfl.split(',')
      self.tf[term] = tfl#map(float, tfl)
      #read idf
      self.idf[term] = float(idf)

#     print(list(self.tf['blue']))
    file.close()

    print('Index loaded\n')
    print(len(self.index))

  def prepareParams(self):
    self.stopwords = set(stopwords.words('english'))
    self.dataFile = FLICKR_FILE_GEN
    self.indexFile = FLICKR_INVERTED_IDX_FILE
    self.stemmer = SnowballStemmer('english') #PorterStemmer()
    self.lemmatizer = WordNetLemmatizer()

  def detectQueryType(self, query):
    if '"' in query:
      return QueryType.PhQ
    else:
      return QueryType.FTQ

  def getTerms(self, doc, noReduction = False, uniqueTermsOnly = False):
    #print('Original\n'+doc)
    doc = doc.lower()
    #print('lowered\n\n'+doc)
    doc = re.sub(r'[^a-z0-9 ]',' ',doc) #put spaces instead of non-alphanumeric characters
    terms = doc.split()

    if not noReduction:
        terms = [term for term in terms if term not in self.stopwords]
        # terms = [self.lemmatizer.lemmatize(term) for term in terms]
        terms = [self.stemmer.stem(term) for term in terms]

    if uniqueTermsOnly:
        terms = (dict.fromkeys(terms))
    #print('Terms:\n\n')
    #print(terms)
    return terms

  def dotProduct(self, vec1, vec2):
    if len(vec1)!=len(vec2):
      return 0
    return dot(vec1, vec2)#/(norm(vec1)*norm(vec2))

  def rankDocuments(self, terms, docs):
    docVectors = defaultdict(lambda: [0]*len(terms))

    queryVector = [0] * len(terms)
    print('Ranking1')
    print(datetime.datetime.now())
    for termIndex, term in enumerate(terms):
      if term not in self.index:
        continue
      print('Ranking2: '+str(datetime.datetime.now()))
      queryVector[termIndex] = self.idf[term]
    #   print(term)
    #   print('++++++++++++++++++++++++++++++++++++++++++')
    #   print(self.index[term])
    #   print('------------------------------------------')
      for docIndex, (doc, postings) in enumerate(self.index[term]):
#         pass
        if doc in docs:
          tfScores = list(self.tf[term])
        #   print(tfScores)
          docVectors[doc][termIndex] = float(tfScores[docIndex])
        #   if doc == '4771139963':
        #   print(doc)
        #   print(term)
        #   print(docVectors[doc])
#       print('Ranking3: '+str(datetime.datetime.now()))
    print(queryVector)
    docScores=[[self.dotProduct(curDocVec, queryVector), doc, curDocVec, queryVector] for doc, curDocVec in docVectors.items()]
    print('Ranking4')
    print(datetime.datetime.now())
    # print(docScores[0])
    docScores.sort(reverse=True)
    resultDocs=[x for x in docScores][:MAX_NO_RESULT]

    #print('\n'.join(resultDocs), '\n')

    return resultDocs


  def performFreeTextQuery(self, query):
    query=self.getTerms(query)
    if len(query)==0:
      print('Empty')
      return []

    print(query)
    docList=set()
    for term in query:
      print('Looking for '+term)
      try:
        posting = self.index[term]
        docs = [x[0] for x in posting]
        docList = docList | set(docs)
      except:
        #term not in index
        pass

    docList = list(docList)

    print(len(docList))
    if len(docList)==0:
      print('Not Found')

    return self.rankDocuments(query, docList)


  def getPostings(self, terms):
    #all terms in the list are guaranteed to be in the index
    return [ self.index[term] for term in terms ]

  def getDocsFromPostings(self, postings):
    #no empty list in postings
    return [ [x[0] for x in p] for p in postings ]

  def phraseQueryDocs(self, query):
    phraseDocs = []
    length = len(query)

    for term in query:
      if term not in self.index:
        return []
    postings = self.getPostings(query)
    docs = self.getDocsFromPostings(postings)
    docs = self.intersectLists(docs)

    for i in range(len(postings)):
      postings[i]=[x for x in postings[i] if x[0] in docs]

    postings = copy.deepcopy(postings)

    for i in range(len(postings)):
      for j in range(len(postings[i])):
        postings[i][j][1] = [x-i for x in postings[i][j][1]]

    result = []
    for i in range(len(postings[0])):
      docList = self.intersectLists([x[i][1] for x in postings])
      if docList == []:
        continue
      else:
        result.append(postings[0][i][0])

    return result


  def performPhraseQuery(self, query):
    originalQuery = query

    query = self.getTerms(query)
    if len(query) == 0:
      print('Empty')
      return

    phraseDocs = self.phraseQueryDocs(query)

    print(' '.join(map(str, phraseDocs)))
    if len(phraseDocs)==0:
      print('Not Found')

    return self.rankDocuments(query, phraseDocs)


  def intersectLists(self, lists):
    if len(lists) == 0:
        return []
    #start intersecting from the smaller list
    lists.sort(key=len)
    return list(reduce(lambda x,y: set(x)&set(y),lists))



  def performQuery(self, query):
#     self.prepareParams()
#     self.readIndex()

    queryType = self.detectQueryType(query)

    docs = []

    if queryType == QueryType.FTQ:
      docs = self.performFreeTextQuery(query)
    elif queryType == QueryType.PhQ:
      docs = self.performPhraseQuery(query)

    print(docs)
    docRetriever = CaptionDocRetriever()
    # print(type(docs[0]))
    docs=[docs[i] for i in range(min(MAX_NO_RESULT, len(docs)))]
    # print('Returned doc length: '+str(len(docs)))
    # print(docs)

    tf_idf_scores = [x[0] for x in docs]
    # print(scores)
    docIds = [x[1] for x in docs]
    # print(docIds)
    tf_scores = [x[2] for x in docs]

    idf_scores = [x[3] for x in docs]

    # print(idf_scores)

    docItems = docRetriever.retrieveDocs(docIds)
    # print(docItems)



    return (docItems, tf_idf_scores, tf_scores, idf_scores)


if __name__ == '__main__':
  queryHandler = ImageQueryHandler()
  queryHandler.prepareParams()
  queryHandler.readIndex()
  result = queryHandler.performQuery('man surfing')
#   print(result)
  print('Search complete')