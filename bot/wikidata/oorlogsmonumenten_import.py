#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Oorlogsmonumenten ding.

"""
import pywikibot
from pywikibot import pagegenerators
import re
import pywikibot.data.sparql
import datetime
import posixpath
import hashlib
import io
import base64
import tempfile
import os
import time
import itertools
import copy
import requests
import csv

class MonumentBot:
    """
    A bot to enrich and create paintings on Wikidata
    """
    def __init__(self, dictGenerator, create=False):
        """
        Arguments:
            * generator    - A generator that yields Dict objects.
            The dict in this generator needs to contain 'idpid' and 'collectionqid'
            * create       - Boolean to say if you want to create new items or just update existing

        """
        firstrecord = next(dictGenerator)
        self.generator = itertools.chain([firstrecord], dictGenerator)
        self.repo = pywikibot.Site().data_repository()
        self.create = create
        
        self.idProperty = firstrecord.get(u'idpid')
        self.collectionqid = firstrecord.get(u'collectionqid')
        self.collectionitem = pywikibot.ItemPage(self.repo, self.collectionqid)
        self.artworkIds = self.fillCache(self.collectionqid,self.idProperty)

    def fillCache(self, collectionqid, idProperty):
        '''
        Build an ID cache so we can quickly look up the id's for property

        '''
        result = {}
        sq = pywikibot.data.sparql.SparqlQuery()

        # FIXME: Do something with the collection qualifier
        #query = u'SELECT ?item ?id WHERE { ?item wdt:P195 wd:%s . ?item wdt:%s ?id }' % (collectionqid, idProperty)
        if collectionqid:
            query = u"""SELECT ?item ?id WHERE {
            ?item wdt:P195 wd:%s .
            ?item p:%s ?idstatement .
            ?idstatement pq:P195 wd:%s .
            ?idstatement ps:%s ?id }""" % (collectionqid, idProperty, collectionqid, idProperty)
        else:
            query = u"""SELECT ?item ?id WHERE {
            ?item wdt:%s ?id  .
            }""" % (idProperty)
        sq = pywikibot.data.sparql.SparqlQuery()
        queryresult = sq.select(query)

        for resultitem in queryresult:
            qid = resultitem.get('item').replace(u'http://www.wikidata.org/entity/', u'')
            result[resultitem.get('id')] = qid
        pywikibot.output(u'The query "%s" returned %s items' % (query, len(result)))
        return result
                        
    def run(self):
        """
        Starts the robot.
        """
            
        for metadata in self.generator:
            # Buh, for this one I know for sure it's in there
            
            #print metadata[u'id']
            #print metadata[u'url']

            # Do some url magic so that all url fields are always filled
            if not metadata.get('refurl'):
                metadata['refurl']=metadata['url']
            if not metadata.get('idrefurl'):
                metadata['idrefurl']=metadata['refurl']
            if not metadata.get('describedbyurl'):
                metadata['describedbyurl']=metadata['url']

            
            artworkItem = None
            newclaims = []
            if metadata[u'id'] in self.artworkIds:
                artworkItemTitle = self.artworkIds.get(metadata[u'id'])
                print (artworkItemTitle)
                artworkItem = pywikibot.ItemPage(self.repo, title=artworkItemTitle)

            elif self.create:
                #Break for now
                #print u'Let us create stuff'
                #continue
                #print u'WTFTFTFTFT???'
                
                #print 'bla'


                data = {'labels': {},
                        'descriptions': {},
                        }

                # loop over stuff
                if metadata.get('title'):
                    for lang, label in metadata['title'].items():
                        data['labels'][lang] = {'language': lang, 'value': label}

                if metadata.get('description'):
                    for lang, description in metadata['description'].items():
                        data['descriptions'][lang] = {'language': lang, 'value': description}
                
                identification = {}
                summary = u'Creating new item with data from %s ' % (metadata[u'url'],)
                pywikibot.output(summary)
                try:
                    result = self.repo.editEntity(identification, data, summary=summary)
                except pywikibot.data.api.APIError:
                    ## TODO: Check if this is pywikibot.OtherPageSaveError too
                    ## We got ourselves a duplicate label and description, let's correct that by adding collection and the id
                    pywikibot.output(u'Oops, already had that one. Trying again')
                    for lang, description in metadata['description'].items():
                        data['descriptions'][lang] = {'language': lang, 'value': u'%s (%s %s)' % (description, metadata['inception'], metadata['id'],) }
                    result = self.repo.editEntity(identification, data, summary=summary)
                    pass

                # Crash here
                artworkItemTitle = result.get(u'entity').get('id')

                # Wikidata is sometimes lagging. Wait for 10 seconds before trying to actually use the item
                time.sleep(10)
                
                artworkItem = pywikibot.ItemPage(self.repo, title=artworkItemTitle)

                # Add to self.artworkIds so that we don't create dupes
                self.artworkIds[metadata[u'id']]=artworkItemTitle

                # Add the id to the item so we can get back to it later
                newclaim = pywikibot.Claim(self.repo, self.idProperty)
                newclaim.setTarget(metadata[u'id'])
                pywikibot.output('Adding new id claim to %s' % artworkItem)
                artworkItem.addClaim(newclaim)

                #self.addReference(artworkItem, newclaim, metadata[u'idrefurl'])
                
                #newqualifier = pywikibot.Claim(self.repo, u'P195') #Add collection, isQualifier=True
                #newqualifier.setTarget(self.collectionitem)
                #pywikibot.output('Adding new qualifier claim to %s' % artworkItem)
                #newclaim.addQualifier(newqualifier)

                #collectionclaim = pywikibot.Claim(self.repo, u'P195')
                #collectionclaim.setTarget(self.collectionitem)
                #pywikibot.output('Adding collection claim to %s' % artworkItem)
                #artworkItem.addClaim(collectionclaim)

                ## Add the date they got it as a qualifier to the collection
                #if metadata.get(u'acquisitiondate'):
                #    if type(metadata[u'acquisitiondate']) is int or (len(metadata[u'acquisitiondate'])==4 and \
                #                                                   metadata[u'acquisitiondate'].isnumeric()): # It's a year
                #        acdate = pywikibot.WbTime(year=metadata[u'acquisitiondate'])
                #        colqualifier = pywikibot.Claim(self.repo, u'P580')
                #        colqualifier.setTarget(acdate)
                #        pywikibot.output('Adding new acquisition date qualifier claim to collection on %s' % artworkItem)
                #        collectionclaim.addQualifier(colqualifier)
                ## FIXME: Still have to rewrite this part
                '''
                if metadata.get(u'acquisitiondate'):
                    colqualifier = pywikibot.Claim(self.repo, u'P580')
                    acdate = None
                    if len(painting[u'acquisitiondate'])==4 and painting[u'acquisitiondate'].isnumeric(): # It's a year
                        acdate = pywikibot.WbTime(year=painting[u'acquisitiondate'])
                    elif len(painting[u'acquisitiondate'].split(u'-', 2))==3:
                        (acday, acmonth, acyear) = painting[u'acquisitiondate'].split(u'-', 2)
                        acdate = pywikibot.WbTime(year=int(acyear), month=int(acmonth), day=int(acday))
                    if acdate:
                        colqualifier.setTarget(acdate)

                '''
                
                #self.addReference(artworkItem, collectionclaim, metadata[u'refurl'])


            
            if artworkItem and artworkItem.exists():
                metadata['wikidata'] = artworkItem.title()

                data = artworkItem.get()
                claims = data.get('claims')


                # Add missing labels
                # FIXME: Move to a function
                # FIXME Do something with aliases too
                labels = data.get('labels')
                if metadata.get('title'):
                    labelschanged = False
                    for lang, label in metadata['title'].items():
                        if lang not in labels:
                            labels[lang] = label
                            labelschanged = True
                    if labelschanged:
                        summary = u'Adding missing label(s) from %s' % (metadata.get(u'refurl'),)
                        try:
                            artworkItem.editLabels(labels, summary=summary)
                        except pywikibot.OtherPageSaveError:
                            # Just skip it for no
                            pywikibot.output(u'Oops, already had that label/description combination. Skipping')
                            pass

                """
                # Add missing descriptions
                # FIXME Move to a function
                descriptions = copy.deepcopy(data.get('descriptions'))
                if metadata.get('description'):
                    descriptionschanged = False
                    for lang, description in metadata['description'].items():
                        if lang not in descriptions:
                            descriptions[lang] = description
                            descriptionschanged = True
                    if descriptionschanged:
                        summary = u'Adding missing description(s) from %s' % (metadata.get(u'refurl'),)
                        try:
                            artworkItem.editDescriptions(descriptions, summary=summary)
                        except pywikibot.exceptions.OtherPageSaveError: # pywikibot.data.api.APIError:
                            # We got ourselves a duplicate label and description, let's correct that by adding collection and the id
                            descriptions = copy.deepcopy(data.get('descriptions'))
                            pywikibot.output(u'Oops, already had that label/description combination. Trying again')
                            for lang, description in metadata['description'].items():
                                if lang not in descriptions:
                                    descriptions[lang] = u'%s (%s %s)' % (description,
                                                                             metadata['collectionshort'],
                                                                             metadata['id'],)
                            artworkItem.editDescriptions(descriptions, summary=summary)
                            pass
                #print claims
                """

                # instance of
                self.addItemStatement(artworkItem, u'P31', metadata.get(u'instanceofqid'), metadata.get(u'refurl'))

                # country
                self.addItemStatement(artworkItem, u'P17', metadata.get(u'countryqid'), metadata.get(u'refurl'))

                # adminlocation
                self.addItemStatement(artworkItem, u'P131', metadata.get(u'adminlocationqid'), metadata.get(u'refurl'))

                # location
                self.addItemStatement(artworkItem, u'P276', metadata.get(u'locationqid'), metadata.get(u'refurl'))

                # creator
                self.addItemStatement(artworkItem, u'P170', metadata.get(u'creatorqid'), metadata.get(u'refurl'))

                # genre
                self.addItemStatement(artworkItem, u'P136', metadata.get(u'genreqid'), metadata.get(u'refurl'))



                # Inception
                if u'P571' not in claims and metadata.get(u'inception'):
                    if type(metadata[u'inception']) is int or (len(metadata[u'inception'])==4 and \
                                                                   metadata[u'inception'].isnumeric()): # It's a year
                        newdate = pywikibot.WbTime(year=metadata[u'inception'])
                        newclaim = pywikibot.Claim(self.repo, u'P571')
                        newclaim.setTarget(newdate)
                        pywikibot.output('Adding date of creation claim to %s' % artworkItem)
                        artworkItem.addClaim(newclaim)
                
                        self.addReference(artworkItem, newclaim, metadata[u'refurl'])
                        # TODO: Implement circa


                if metadata.get('image') and u'P18' not in claims:
                    print u'no image found'
                    # Construct
                    newclaim = pywikibot.Claim(self.repo, u'P18')
                    commonssite = pywikibot.Site("commons", "commons")
                    imagelink = pywikibot.Link(metadata.get('image'), source=commonssite, defaultNamespace=6)
                    image = pywikibot.ImagePage(imagelink)
                    if image.isRedirectPage():
                        image = pywikibot.ImagePage(image.getRedirectTarget())
                    if not image.exists():
                        pywikibot.output('[[%s]] doesn\'t exist so I can\'t link to it' % (image.title(),))
                    else:
                        newclaim.setTarget(image)
                        pywikibot.output('Adding %s --> %s' % (newclaim.getID(), newclaim.getTarget()))
                        artworkItem.addClaim(newclaim)

                if metadata.get('commonscat') and u'P373' not in claims:
                    print u'no image found'
                    # Construct
                    newclaim = pywikibot.Claim(self.repo, u'P373')
                    commonssite = pywikibot.Site("commons", "commons")
                    commonslink = pywikibot.Link(metadata.get('commonscat'), source=commonssite, defaultNamespace=14)
                    commonscat = pywikibot.Page(commonslink)
                    if commonscat.isRedirectPage():
                        commonscat = pywikibot.Page(commonscat.getRedirectTarget())
                    if not commonscat.exists():
                        pywikibot.output('[[%s]] doesn\'t exist so I can\'t link to it' % (commonscat.title(),))
                    else:
                        newclaim.setTarget(commonscat.title(withNamespace=False))
                        pywikibot.output('Adding %s --> %s' % (newclaim.getID(), newclaim.getTarget()))
                        artworkItem.addClaim(newclaim)

                if metadata.get('lat') and metadata.get('lon') and u'P625' not in claims:
                    print u'no coordinates found'
                    # Build coordinates and add them
                    coordinate = pywikibot.Coordinate(metadata.get('lat'), metadata.get('lon'), dim=100)
                    newclaim = pywikibot.Claim(self.repo, u'P625')
                    newclaim.setTarget(coordinate)
                    pywikibot.output(u'Adding %s, %s to %s' % (coordinate.lat, coordinate.lon, artworkItem.title()))
                    artworkItem.addClaim(newclaim)


    def addImageSuggestion(self, item, metadata):
        """
        Add an image that can be uploaded to Commons

        It will also add the suggestion if the item already has an image, but new one is of much better quality

        :param item: The artwork item to work on
        :param metadata: All the metadata about this artwork, should contain the imageurl field
        :return:
        """
        claims = item.get().get('claims')

        if not metadata.get(u'imageurl'):
            # Nothing to add
            return
        if u'P4765' in claims:
            # Already has a suggestion
            return

        if u'P18' in claims:
            newimage = requests.get(metadata.get(u'imageurl'), stream=True)
            if not newimage.headers.get('Content-length'):
                return
            if not newimage.headers.get('Content-length').isnumeric():
                return
            newimagesize = int(newimage.headers['Content-length'])
            #print (u'Size of the new image is %s according to the headers' % (newimagesize,))
            if newimagesize < 500000:
                # Smaller than 500KB is just too small to bother check to replace
                return

            for imageclaim in claims.get(u'P18'):
                currentsize = imageclaim.getTarget().latest_file_info.size
                #print (u'Size of the current image is %s' % (currentsize,))
                # New image should at least be 4 times larger
                if currentsize * 4 > newimagesize:
                    return

        newclaim = pywikibot.Claim(self.repo, u'P4765')
        newclaim.setTarget(metadata[u'imageurl'])
        pywikibot.output('Adding commons compatible image available at URL claim to %s' % item)
        item.addClaim(newclaim)

        if metadata.get(u'imageurlformat'):
            newqualifier = pywikibot.Claim(self.repo, u'P2701')
            newqualifier.setTarget(pywikibot.ItemPage(self.repo, metadata.get(u'imageurlformat')))
            pywikibot.output('Adding new qualifier claim to %s' % item)
            newclaim.addQualifier(newqualifier)

        newqualifier = pywikibot.Claim(self.repo, u'P2699')
        newqualifier.setTarget(metadata[u'describedbyurl'])
        pywikibot.output('Adding new qualifier claim to %s' % item)
        newclaim.addQualifier(newqualifier)

        if metadata.get('title'):
            if metadata.get('title').get(u'en'):
                title = pywikibot.WbMonolingualText(metadata.get('title').get(u'en'), u'en')
            else:
                lang = list(metadata.get('title').keys())[0]
                title = pywikibot.WbMonolingualText(metadata.get('title').get(lang), lang)
            newqualifier = pywikibot.Claim(self.repo, u'P1476')
            newqualifier.setTarget(title)
            pywikibot.output('Adding new qualifier claim to %s' % item)
            newclaim.addQualifier(newqualifier)

        if metadata.get('creatorname'):
            newqualifier = pywikibot.Claim(self.repo, u'P2093')
            newqualifier.setTarget(metadata.get('creatorname'))
            pywikibot.output('Adding new qualifier claim to %s' % item)
            newclaim.addQualifier(newqualifier)

        if metadata.get(u'imageurllicense'):
            newqualifier = pywikibot.Claim(self.repo, u'P275')
            newqualifier.setTarget(pywikibot.ItemPage(self.repo, metadata.get(u'imageurllicense')))
            pywikibot.output('Adding new qualifier claim to %s' % item)
            newclaim.addQualifier(newqualifier)

    def addItemStatement(self, item, pid, qid, url):
        '''
        Helper function to add a statement
        '''
        if not qid:
            return False

        claims = item.get().get('claims')
        if pid in claims:
            return
        
        newclaim = pywikibot.Claim(self.repo, pid)
        destitem = pywikibot.ItemPage(self.repo, qid)
        if destitem.isRedirectPage():
            destitem = destitem.getRedirectTarget()

        newclaim.setTarget(destitem)
        pywikibot.output(u'Adding %s->%s to %s' % (pid, qid, item))
        item.addClaim(newclaim)
        self.addReference(item, newclaim, url)
        
    def addReference(self, item, newclaim, url):
        """
        Add a reference with a retrieval url and todays date
        """
        return
        """
        pywikibot.output('Adding new reference claim to %s' % item)
        refurl = pywikibot.Claim(self.repo, u'P854') # Add url, isReference=True
        refurl.setTarget(url)
        refdate = pywikibot.Claim(self.repo, u'P813')
        today = datetime.datetime.today()
        date = pywikibot.WbTime(year=today.year, month=today.month, day=today.day)
        refdate.setTarget(date)
        newclaim.addSources([refurl, refdate])
        """

def israelArtistsOnWikidata():
    '''
    Just return all the  Information Center for Israeli Art artist ID (P1736) as a dict
    :return: Dict
    '''
    result = {}
    query = u'SELECT ?item ?id WHERE { ?item wdt:P1736 ?id . ?item wdt:P31 wd:Q5 } LIMIT 12345678'
    sq = pywikibot.data.sparql.SparqlQuery()
    queryresult = sq.select(query)

    for resultitem in queryresult:
        qid = resultitem.get('item').replace(u'http://www.wikidata.org/entity/', u'')
        result[resultitem.get('id')] = qid
    return result

def getOorlogsmonumentenDataGenerator():
    """
    Generator to parse https://nl.wikipedia.org/w/index.php?title=Speciaal:VerwijzingenNaarHier/Sjabloon:Tabelrij_oorlogsmonument_Nederland&namespace=0&limit=500
    """

    site = pywikibot.Site('nl', 'wikipedia')

    row_template = pywikibot.Page(site, 'Template:Tabelrij oorlogsmonument Nederland')

    trans_gen = pagegenerators.ReferringPageGenerator(row_template, onlyTemplateInclusion=True)
    filtered_gen = pagegenerators.NamespaceFilterPageGenerator(trans_gen, [0], site=site)

    for page in filtered_gen:
        print page.title()
        templates = page.templatesWithParams()
        for (template, params) in templates:
            #print template
            if template.title(with_ns=False)==u'Tabelrij oorlogsmonument Nederland': #
                metadata = {}

                for param in params:
                    #print param
                    (field, _, value) = param.partition(u'=')
                    # Remove leading or trailing spaces
                    field = field.strip()
                    metadata[field] = value
                    #print field
                    #print value
                yield metadata


def getOorlogsmonumentenGenerator(dictGen):

    fieldnames = [u'type_c',
                  u'onthulling',
                  u'herdachte_groep',
                  u'objnr',
                  u'adres',
                  u'image',
                  u'ontwerper',
                  u'lon',
                  u'onthulling_sort',
                  u'postcode',
                  u'type_obj',
                  u'lat',
                  u'objectnaam',
                  u'gemeente',
                  u'plaats',
                  ]

    for entry in dictGen:
        #print entry
        metadata = {}
        metadata[u'url'] = u'https://nl.wikipedia.org/w/index.php?title=Speciaal:VerwijzingenNaarHier/Sjabloon:Tabelrij_oorlogsmonument_Nederland&namespace=0&limit=500'
        if not entry.get(u'objnr') or not entry.get(u'objnr').isdigit():
            continue

        metadata['idpid'] = u'P3638'
        metadata['id'] = entry.get(u'objnr')

        if entry.get(u'image'):
            metadata[u'image'] = entry.get(u'image')

        if entry.get(u'lat') and entry.get(u'lon'):
            metadata[u'lat'] = float(entry.get(u'lat'))
            metadata[u'lon'] = float(entry.get(u'lon'))
        yield metadata
        """
        



            if field==u'id':
                    
                elif field==u'title':
                    metadata['title'] = {}
                    metadata['title']['en'] = value
                elif field==u'artist':
                    # Extract the name of the artist
                    artistregex = u'^\[\[([^\]]+)\]\]$'
                    namematch = re.match(artistregex, value)
                    if not namematch:
                        name = value.replace(u'[', u'').replace(u']', u'')
                    else:
                        name = namematch.group(1)
                    metadata['creatorname'] = name
                    metadata['description'] = { u'en' : u'%s by %s' % (u'sculpture', metadata.get('creatorname'),),
                                            }
                    # Try to get a Qid based on Wikipedia link. Might have a collision here
                    creatorpage = pywikibot.Page(site, name)
                    if creatorpage.exists():
                        if creatorpage.isRedirectPage():
                            creatorpage = creatorpage.getRedirectTarget()
                        creatoritem = creatorpage.data_item()
                        if metadata.get('creatorqid'):
                            crash
                        metadata['creatorqid'] = creatoritem.title()

                elif field==u'extArtistLink':
                    # Extract the id of the artist from the URL. Might have a collision here
                    artistlinkregex = u'^\s*http\:\/\/www\.imj\.org\.il\/artcenter\/newsite\/en\/\?artist\=(\d+)\s*$'
                    artistlinkmatch = re.match(artistlinkregex, value)
                    if artistlinkmatch:
                        artistid = artistlinkmatch.group(1)
                        if israelArtists.get(artistid):
                            artistqid = israelArtists.get(artistid)
                            if artistqid:
                                if not metadata.get('creatorqid'):
                                    metadata['creatorqid'] = artistqid
                                elif metadata['creatorqid'] == artistqid:
                                    print u'Both systems agree about the creator'
                                else:
                                    print u'PANIC PANIC PANIC'
                                    print u'PANIC PANIC PANIC'
                                    print u'PANIC PANIC PANIC'
                                    print u'PANIC PANIC PANIC'
                                    print u'Found conflicting Wikidata id\'s %s & %s' % (metadata.get('creatorqid'),
                                                                                         artistqid,)
                                    time.sleep(5)


                elif field==u'description':
                    # Not useful for me
                    continue
                elif field==u'year':
                    metadata['inception'] = value
                elif field==u'type':
                    # Always sculpture or empty
                    continue
                elif field==u'fop':
                    # Awesome, you have FOP
                    continue
                    print u'bla'
                elif field==u'address':
                    if value in locations:
                        metadata[u'locationqid'] = locations.get(value)
                elif field==u'district':
                    print u'bla'
                elif field==u'region':
                    print u'bla'
                elif field==u'municipality':
                    if value in municipalities:
                        metadata[u'adminlocationqid'] = municipalities.get(value)
                    print u'bla'
                elif field==u'lat':
                    if value:
                        metadata[u'lat'] = float(value)
                elif field==u'long':
                    if value:
                        metadata[u'lon'] = float(value)
                elif field==u'image':
                    metadata['image'] = value
                elif field==u'placecat':
                    if value in locations:
                        metadata[u'locationqid'] = locations.get(value)
                elif field==u'commonscat':
                    metadata['commonscat'] = value
                else:
                    print u'PANIC PANIC PANIC'
                    print u'PANIC PANIC PANIC'
                    print u'PANIC PANIC PANIC'
                    print u'PANIC PANIC PANIC'
                    print u'Found unkown field %s with contents %s' % (field, value)
                    time.sleep(5)
            if metadata.get('id'):
        """

def makeCSVfile(generator):
    with open('/tmp/oorlogsmonumenten.tsv', 'wb') as tsvfile:
        fieldnames = [u'type_c',
                      u'onthulling',
                      u'herdachte_groep',
                      u'objnr',
                      u'adres',
                      u'image',
                      u'ontwerper',
                      u'lon',
                      u'onthulling_sort',
                      u'postcode',
                      u'type_obj',
                      u'lat',
                      u'objectnaam',
                      u'gemeente',
                      u'plaats',
                      ]

        writer = csv.DictWriter(tsvfile, fieldnames, dialect='excel-tab')

        writer.writeheader()

        for monument in generator:
            print monument
            monumentdict = {}
            for key in monument.keys():
                if key and key in fieldnames:
                    monumentdict[key] = monument[key].encode(u'utf-8')
                    print key
                    print monument.get(key)
            writer.writerow(monumentdict)

def main(*args):
    dryrun = False
    makecsv = False
    create = False
    dictGen = getOorlogsmonumentenDataGenerator()

    for arg in pywikibot.handle_args(args):
        if arg.startswith('-dry'):
            dryrun = True
        elif arg.startswith('-makecsv'):
            makecsv = True
        elif arg.startswith('-create'):
            create = True

    if makecsv:
        makeCSVfile(dictGen)
    else:
        metadatagen = getOorlogsmonumentenGenerator(dictGen)

    if dryrun:
        count = 0
        for sculpture in metadatagen:
            print (sculpture)
            count += 1
        print(count)
    else:
        monumentBot = MonumentBot(metadatagen, create=create)
        monumentBot.run()

if __name__ == "__main__":
    main()
