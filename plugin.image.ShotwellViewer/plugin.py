#!/usr/bin/python

import sys
import os
import urllib
import urlparse
import xbmcgui
import xbmcplugin
import xbmcaddon
import datetime
from shotwell import ShotwellAccess

# set some global options
base_url = sys.argv[0]
addon_handle = int(sys.argv[1])
xbmcplugin.setContent(addon_handle, 'pictures')
        
# id = xbmc.getInfoLabel('Container.Viewmode')

def build_url(query):
    return base_url + '?' + urllib.urlencode(query)

def getDayDateFromUnixTimestamp(timestamp):
    date = datetime.datetime.utcfromtimestamp(timestamp)
    return str(date.day) + "." + str(date.month) + "." + str(date.year)
    
def getYearFromUnixTimestamp(timestamp):
    date = datetime.datetime.utcfromtimestamp(timestamp)
    return str(date.year)

class ShotwellViewer:
    
    def getShotwellDatabasePath(self):
        __settings__ = xbmcaddon.Addon()
        path = None
        db_path_from_settings = __settings__.getSetting( "shotwelldb" )
        if db_path_from_settings is not None and db_path_from_settings!= "":
            path = db_path_from_settings
        else:
            path = os.environ['HOME'] + '/.local/share/shotwell/data/photo.db'
            
        if path == '' or not os.path.exists(path):
            return None
        
        return path
        
    def getSourceTargetPrefix(self):
        __settings__ = xbmcaddon.Addon()
        source = __settings__.getSetting( "sourcepath" )
        if source is None:
            source = ""
        target = __settings__.getSetting( "targetpath" )
        if target is None:
            target = ""
        
        return source, target
        
    def getSortEventsDescending(self):
        __settings__ = xbmcaddon.Addon()
        descending = __settings__.getSetting( "sort_events_desc" )
        if descending is None:
            descending = True
        return descending == "true"
        
    def getSortPicturesAscending(self):
        __settings__ = xbmcaddon.Addon()
        ascending = __settings__.getSetting( "sort_pictures_asc" )
        if ascending is None:
            ascending = True
        return ascending == "true"
        
    
    def __init__(self):
        self.args = args = urlparse.parse_qs(sys.argv[2][1:]) 
        self.shotwelldb = self.getShotwellDatabasePath()
        self.sourcePathPrefix,  self.targetPathPrefix = self.getSourceTargetPrefix()
        self.sortEventsDescending = self.getSortEventsDescending()
        #self.sortPicturesDescending = not self.getSortPicturesAscending()
        
    def getProperPath(self, filepath):
        if self.sourcePathPrefix != "" and filepath.startswith(self.sourcePathPrefix):
            return self.targetPathPrefix + "/" + filepath[len(self.sourcePathPrefix):]
        else:
            return filepath

    def addCategoryToTitlePage(self, category):
        url = build_url({'category': category})
        li = xbmcgui.ListItem(category)
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url,
                                    listitem=li, isFolder=True)    

    def createTitlePage(self):
        self.addCategoryToTitlePage('Saved Searches')
        self.addCategoryToTitlePage('Events')
     
        xbmcplugin.endOfDirectory(addon_handle)

    def createSavedSearchesTitlePage(self):
        category = 'Saved Searches'
        v = ShotwellAccess(self.shotwelldb)
        searches = v.getSavedSearches()
        searches.sort(key=lambda savedSearch: savedSearch['earliest_time'])
        for search in searches:
            url = build_url({
                    'category': category, 
                    'search_id': search['id']})
            picturePath = self.getProperPath(search['picture_representation']['filename'])
            li = xbmcgui.ListItem(search['name'], iconImage=picturePath)
            xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)     
            
        xbmcplugin.endOfDirectory(addon_handle)
    
    def createPicturePage(self, pictures):
        for picture in pictures:
            url = self.getProperPath(picture['filename'])
            title = picture['title']
            if title is None:
                title = os.path.basename(url)
            li = xbmcgui.ListItem(title, iconImage=url)
            xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=False)     
            
        xbmcplugin.endOfDirectory(addon_handle)
    
    def createSavedSearchPage(self, searchId):
        v = ShotwellAccess(self.shotwelldb)
        searchInfo = v.getSavedSearchInfo(searchId)
        pictures = v.getPicturesOfSavedSearch(searchInfo)
        self.createPicturePage(pictures)

    def createSavedSearchesPage(self):
        searchIds = self.args.get('search_id', None)
        
        if searchIds is None:
            self.createSavedSearchesTitlePage()
        else:
            self.createSavedSearchPage(searchIds[0])
    
    def getYearsOfEvents(self, events):
        result = []
        for event in events:
            year = getYearFromUnixTimestamp(event['startrange'])
            if year not in result:
                result += [year]
            
            year = getYearFromUnixTimestamp(event['endrange'])
            if year not in result:
                result += [year]
        return result
    
    def createEventsTitlePage(self):
        category = 'Events'
        v = ShotwellAccess(self.shotwelldb)
        events = v.getEvents()
        years = self.getYearsOfEvents(events)
        years.sort(reverse=self.sortEventsDescending)
        for year in years:
            url = build_url({
                    'category': category, 
                    'event_year': year})
            name = year
            li = xbmcgui.ListItem(name)
            xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)     
            
        xbmcplugin.endOfDirectory(addon_handle)
    
    def filterEventYears(self, events, year):
        result = []
        for event in events:
            year1 = getYearFromUnixTimestamp(event['startrange'])
            year2 = getYearFromUnixTimestamp(event['endrange'])
            if year1==year or year2==year:
                result += [event]
        return result
    
    def createEventsYearPage(self, year):
        category = 'Events'
        v = ShotwellAccess(self.shotwelldb)
        events = self.filterEventYears(v.getEvents(), year)
        events.sort(key=lambda event: event['startrange'], reverse=self.sortEventsDescending)
        for event in events:
            url = build_url({
                    'category': category,
                    'event_year': year,
                    'event_id': event['eventid']})
            start = getDayDateFromUnixTimestamp(event['startrange'])
            end = getDayDateFromUnixTimestamp(event['endrange'])
            name = event['name'] 
            if start == end:
                name += " (" + start + ")"
            else:
                name += " (" + start +" - " + end + ")"
            picturePath = self.getProperPath(event['picture_representation']['filename'])
            li = xbmcgui.ListItem(name, iconImage=picturePath)
            xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)     
            
        xbmcplugin.endOfDirectory(addon_handle)
    
    def createEventPage(self, year, eventId, flagged):
        category = 'Events'
        v = ShotwellAccess(self.shotwelldb)
        pictures = v.getPicturesOfEvent(eventId, flagged)
        if not flagged:
            flagged_pictures = v.getPicturesOfEvent(eventId, True)
            if len(flagged_pictures)>0:
                url = build_url({
                        'category': category, 
                        'event_year': year,
                        'event_id': eventId,
                        'event_flagged': "True"})
                name = "Flagged"
                li = xbmcgui.ListItem(name)
                xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)  
            
        self.createPicturePage(pictures)    
    
    def createEventsPage(self):
        eventYears = self.args.get('event_year', None)
        eventIds = self.args.get('event_id', None)
        eventFlaggs = self.args.get('event_flagged', None)
        
        if eventYears is None:
            self.createEventsTitlePage()
        elif eventIds is None:
            self.createEventsYearPage(eventYears[0])
        else:
            flagged = False
            if eventFlaggs is not None and eventFlaggs[0]=="True":
                flagged = True
            self.createEventPage(eventYears[0], eventIds[0], flagged)

    def Main(self):
        categories = self.args.get('category', None)
        if categories is None:
            self.createTitlePage() 
        else:
            category = categories[0]
            if category == 'Saved Searches':
                self.createSavedSearchesPage()
            elif category == 'Events':
                self.createEventsPage()
            else:
                xbmcplugin.endOfDirectory(addon_handle)
        

if (__name__ == "__main__"):
    ShotwellViewer().Main()
