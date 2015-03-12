# -*- encoding: utf-8 -*-

# Dissemin: open access policy enforcement tool
# Copyright (C) 2014 Antonin Delpeuch
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#

from __future__ import unicode_literals

from django.core.exceptions import ObjectDoesNotExist
import re

from papers.utils import create_paper_fingerprint, date_from_dateparts, sanitize_html
from papers.errors import MetadataSourceException
from papers.models import *
from papers.doi import to_doi
from papers.name import to_plain_name, parse_comma_name

from backend.crossref import fetch_metadata_by_DOI
from backend.romeo import fetch_journal
from backend.globals import *

# TODO: this could be a method of ClusteringContextFactory ?
# TODO: implement a dummy relevance classifier for the first phase
def get_or_create_paper(title, author_names, pubdate, doi=None, visibility='VISIBLE'):
    """
    Creates a paper if it is not already present.
    The clustering algorithm is run to decide what authors should be 
    attributed to the paper.
    """
    # If a DOI is present, first look it up
    if doi:
        matches = Publication.objects.filter(doi__exact=doi)
        if matches:
            paper = matches[0].paper
            if visibility == 'VISIBLE' and paper.visibility == 'CANDIDATE':
                paper.visibility = 'VISIBLE'
                paper.save(update_fields=['visibility'])
            return matches[0].paper

    if not title or not author_names or not pubdate:
        raise ValueError("A title, pubdate and authors have to be provided to create a paper.")

    title = sanitize_html(title)

    # Otherwise look up the fingerprint
    plain_names = map(to_plain_name, author_names)
    fp = create_paper_fingerprint(title, plain_names)
    matches = Paper.objects.filter(fingerprint__exact=fp)

    p = None
    if matches:
        p = matches[0]
        if visibility == 'VISIBLE' and p.visibility == 'CANDIDATE':
            p.visibility = 'VISIBLE'
            p.save(update_fields=['visibility'])
    else:
        p = Paper(title=title,
                pubdate=pubdate,
                fingerprint=fp,
                visibility=visibility)
        p.save()
        authors = []
        for author_name in author_names:
            author_name.save_if_not_saved()
            a = Author(name=author_name, paper=p)
            a.save()
            if author_name.is_known:
                clustering_context_factory.clusterAuthorLater(a)
            authors.append(a)

    if doi:
        try:
            metadata = fetch_metadata_by_DOI(doi)
            create_publication(p, metadata)
        except MetadataSourceException as e:
            print "Warning, metadata source exception while fetching DOI "+doi+":\n"+unicode(e)
            pass
    return p

# Merges the second paper into the first one
def merge_papers(first, second):
    # TODO What if the authors are not the same?
    # We should merge the list of authors, so that the order is preserved

    # TODO merge author relations

    if first.pk == second.pk:
        return

    statuses = [first.visibility,second.visibility]
    new_status = 'DELETED'
    for s in VISIBILITY_CHOICES:
        if s[0] in statuses:
            new_status = s[0]
            break
    
    OaiRecord.objects.filter(about=second.pk).update(about=first.pk)
    Publication.objects.filter(paper=second.pk).update(paper=first.pk)
    Annotation.objects.filter(paper=second.pk).update(paper=first.pk)
    if second.last_annotation:
        first.last_annotation = None
        for annot in first.annotation_set.all().order_by('-timestamp'):
            first.last_annotation = annot.status
            break
        first.save(update_fields=['last_annotation'])
    second.delete()
    first.visibility = new_status
    first.update_availability()


# Create a Publication entry based on the DOI metadata
def create_publication(paper, metadata):
    if not metadata:
        return
    if not 'container-title' in metadata or not metadata['container-title']:
        return
    doi = to_doi(metadata.get('DOI',None))
    # Test first if there is no publication with this new DOI
    matches = Publication.objects.filter(doi__exact=doi)
    if matches:
        return matches[0]

    title = metadata['container-title'][:512]
    issn = metadata.get('ISSN',None)
    if issn and type(issn) == type([]):
        issn = issn[0] # TODO pass all the ISSN to the RoMEO interface
    volume = metadata.get('volume',None)
    pages = metadata.get('page',None)
    issue = metadata.get('issue',None)
    date_dict = metadata.get('issued',dict())
    pubdate = None
    if 'date-parts' in date_dict:
        dateparts = date_dict.get('date-parts')[0]
        pubdate = date_from_dateparts(dateparts)
    # for instance it outputs dates like 2014-2-3
    publisher = metadata.get('publisher', None)
    if publisher:
        publisher = publisher[:512]
    pubtype = 'article'

    # Lookup journal
    search_terms = {'jtitle':title}
    if issn:
        search_terms['issn'] = issn
    journal = fetch_journal(search_terms)
    # TODO use the "publisher" info ?


    pub = Publication(title=title, issue=issue, volume=volume,
            pubdate=pubdate, paper=paper, pages=pages,
            doi=doi, pubtype=pubtype, publisher=publisher,
            journal=journal)
    pub.save()
    cur_pubdate = paper.pubdate
    if type(cur_pubdate) != type(pubdate):
        cur_pubdate = cur_pubdate.date()
    if pubdate and pubdate > cur_pubdate:
        paper.pubdate = pubdate
    paper.update_availability()
    return pub

