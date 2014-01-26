import sqlite3

NON_RAW_EXTENSIONS = [
        "jpg", "jpeg", "jpe",
        "tiff", "tif",
        "png",
        "gif",
        "bmp",
        "ppm", "pgm", "pbm", "pnm",        
        # THM are JPEG thumbnails produced by some RAW cameras ... want to support the RAW
        # image but not import their thumbnails
        "thm",        
        # less common
        "tga", "ilbm", "pcx", "ecw", "img", "sid", "cd5", "fits", "pgf",        
        # vector
        "cgm", "svg", "odg", "eps", "pdf", "swf", "wmf", "emf", "xps",        
        # 3D
        "pns", "jps", "mpo"]
        
RAW_EXTENSIONS = [
        "3fr", "arw", "srf", "sr2", "bay", "crw", "cr2", "cap", "iiq", "eip", "dcs", "dcr", "drf",
        "k25", "kdc", "dng", "erf", "fff", "mef", "mos", "mrw", "nef", "nrw", "orf", "ptx", "pef",
        "pxn", "r3d", "raf", "raw", "rw2", "rwl", "rwz", "x3f", "srw"]
        
ALL_EXTENSIONS = NON_RAW_EXTENSIONS + RAW_EXTENSIONS


class TagFilter:
    def __init__(self, context, value):
        self.context = context
        self.value = value
            
class ShotwellAccess:
    
    def __init__(self, database):
        self.database = database
        self.connection = sqlite3.connect(self.database)
        self.cursor = self.connection.cursor()

    def photoIdToSourceId(self, id):
        return "%s%016x"%("thumb",id)

    def getSavedSearches(self):
        searches = []
        self.cursor.execute('select distinct id, name, operator from savedsearchdbtable order by id asc')
        result = self.cursor.fetchall()
        for row in result:
            intermediateSearch = {'id': row[0], 'name': row[1], 'matchtype': row[2], 'picture_representation': None, 'earliest_time': None}
            pictureInfo = self.getFirstMatchOfSavedSearch(intermediateSearch)
            if pictureInfo is not None:
                intermediateSearch['picture_representation'] = pictureInfo
                intermediateSearch['earliest_time'] = pictureInfo['exposure_time']
                searches += [intermediateSearch]
        return searches
    
    def getSavedSearchInfo(self, id):
        search = None
        self.cursor.execute('select distinct id, name, operator from savedsearchdbtable where id = ?', (str(id), ))
        rows = self.cursor.fetchall()
        if len(rows)>0:
            row = rows[0]
            search = {'id': row[0], 'name': row[1], 'matchtype': row[2]}
        
        return search
    
    def getDateSearchConditions(self, savedSearch):
        self.cursor.execute("""select context, date_one, date_two 
                               from savedsearchdbtable as T1 join savedsearchdbtable_date as T2 on T1.id = T2.search_id 
                               where T1.id = ?""", (savedSearch['id'],))
        rows = self.cursor.fetchall()        
        conditions = []
        
        for sresult in rows:            
            if sresult[0] == "BETWEEN":
                conditions += [""" "exposure_time" between '%s' and '%s'"""%(sresult[1], str(int(sresult[2])+86400))] # include the whole second day
            elif sresult[0] == "EXACT":
                conditions += [""" "exposure_time" = %s"""%(sresult[1])]
            elif sresult[0] == "AFTER":
                conditions += [""" "exposure_time" > %s"""%(sresult[1])]
            elif sresult[0] == "BEFORE":
                conditions += [""" "exposure_time" < %s"""%(sresult[1])]
            elif sresult[0] == "IS_NOT_SET":
                conditions += [""" "exposure_time" is NULL"""%(sresult[1])]
            
        return conditions
    
    def getTextSearchConditions(self, savedSearch):
        self.cursor.execute("""select search_type, context, text 
                               from savedsearchdbtable as T1 join savedsearchdbtable_text as T2 on  T1.id = T2.search_id
                               where T1.id = ?""", (savedSearch['id'],))
        rows = self.cursor.fetchall()        
        conditions = []
        
        for sresult in rows:
            comparison = ""
            if sresult[1] == "CONTAINS":
                comparison = " LIKE '%" + sresult[2] + "%'"
            elif sresult[1] == "IS_EXACTLY":
                comparison = " = '" + sresult[2] + "'"
            elif sresult[1] == "STARTS_WITH":
                comparison = " LIKE '%" + sresult[2] + "'"
            elif sresult[1] == "ENDS_WITH":
                comparison = " LIKE '" + sresult[2] + "%'"
            elif sresult[1] == "DOES_NOT_CONTAIN":
                comparison = " LIKE '%" + sresult[2] + "%' IS FALSE"
            elif sresult[1] == "IS_NOT_SET":
                comparison = " IS NULL"
            
            tmpconditions = []
            if sresult[0] == "TAG" or sresult[0] == "ANY_TEXT":
                tmpconditions += ["id in (" + self.concatList(self.getPhotoIdListFromTagCondition(comparison)) + ")"]
            elif sresult[0] == "COMMENT" or sresult[0] == "ANY_TEXT":
                tmpconditions += ["comment " + comparison]
            elif sresult[0] == "EVENT_NAME" or sresult[0] == "ANY_TEXT":
                tmpconditions += ["event_id in (select distinct id from eventtable where name %s)"%(comparison)]
            elif sresult[0] == "FILE_NAME" or sresult[0] == "ANY_TEXT":
                tmpconditions += ["filename " + comparison]
            elif sresult[0] == "TITLE" or sresult[0] == "ANY_TEXT":
                tmpconditions += ["title " + comparison]
            
            if sresult[0] == "ANY_TEXT" and len(tmpconditions)>0:
                condition = tmpconditions[0]
                for con in tmpconditions[1:]:
                    condition += " OR " + con
                tmpconditions = [condition]
            
            conditions += tmpconditions
            
            
        return conditions
    
    def getFlaggedSearchConditions(self, savedSearch):
        self.cursor.execute("""select search_type, flag_state 
                               from savedsearchdbtable as T1 join savedsearchdbtable_flagged as T2 on T1.id = T2.search_id 
                               where T1.id = ?""", (savedSearch['id'],))
        rows = self.cursor.fetchall()        
        conditions = []
        
        for sresult in rows:            
            if sresult[1] == "FLAGGED":
                conditions += ["""(flags & 16) == 16"""]
            else:
                conditions += ["""(flags & 16) == 0"""]
            
        return conditions
    
    def getMediatypeCondition(self, validExtensions):
        condition = ""
        if len(validExtensions)>0:
            ext = validExtensions[0]
            condition = "lower(substr(filename," + str(-len(ext)) + ")) = '" + str(ext.lower()) + "'"
            for ext in validExtensions[1:]:
                condition += " OR lower(substr(filename," + str(-len(ext)) + ")) = '" + str(ext.lower()) + "'"
        
        return condition
    
    def getMediaTypeSearchConditions(self, savedSearch):
        self.cursor.execute("""select search_type, context, type 
                               from savedsearchdbtable as T1 join savedsearchdbtable_mediatype as T2 on T1.id = T2.search_id 
                               where T1.id = ?""", (savedSearch['id'],))
        rows = self.cursor.fetchall()        
        conditions = []
        
        for row in rows:
            prefix = ""
            if row[1]== 'IS_NOT':
                prefix = 'NOT '
            
            if row[2]=='PHOTO_ALL':
                conditions += [prefix + "(" + self.getMediatypeCondition(ALL_EXTENSIONS) + ")"]
            elif row[2]=='PHOTO_RAW':
                conditions += [prefix + "(" + self.getMediatypeCondition(RAW_EXTENSIONS) + ")"]
            else: # not supported media type
                conditions += [prefix + "(filename is NULL and filename is not NULL)"]
        
        return conditions
    
    def getRatingSearchConditions(self, savedSearch):
        self.cursor.execute("""select search_type, rating, context
                               from savedsearchdbtable as T1 join savedsearchdbtable_rating as T2 on T1.id = T2.search_id 
                               where T1.id = ?""", (savedSearch['id'],))
        rows = self.cursor.fetchall()        
        conditions = []
        
        for sresult in rows:
            comparison_operator = "="
            if sresult[2] == "ONLY":
                comparison_operator = "="
            elif sresult[2] == "AND_LOWER":
                comparison_operator = "<="
            elif sresult[2] == "AND_HIGHER":
                comparison_operator = ">="
                
            if sresult[1] == -1: # rejected
                conditions += ["rating " + comparison_operator + " -1"]    
            elif sresult[1] == 0: # unset
                conditions += ["rating " + comparison_operator + " 0"]    
            elif sresult[1] == 1: 
                conditions += ["rating " + comparison_operator + " 1"]
            elif sresult[1] == 2:
                conditions += ["rating " + comparison_operator + " 2"]
            elif sresult[1] == 3:
                conditions += ["rating " + comparison_operator + " 3"]
            elif sresult[1] == 4:
                conditions += ["rating " + comparison_operator + " 4"]
            elif sresult[1] == 5:
                conditions += ["rating " + comparison_operator + " 5"]
        
        return conditions
    
    def getIdFromSourceId(self, sourceId, prefix):
        hex = '0';
        i = len(prefix);
        while i<len(sourceId) and sourceId[i]!='0':
            i += 1
        
        if i<len(sourceId):
            hex = sourceId[i:]
        
        return int(hex, 16)
    
    def concatList(self, list):
        result = ''
        if len(list)>0:            
            result += str(list[0])
            for item in list[1:]:
                result += ', ' + str(item)
            
        return result
            
    def getPhotoIdListFromTagCondition(self, condition):        
        sql = "select photo_id_list from tagtable where name " + condition        
        self.cursor.execute(sql)
        rows = self.cursor.fetchall()
        result = []
        for row in rows:
            tmplist = row[0].split(',')
            for sourceId in tmplist:
                if sourceId.startswith('thumb'):
                    result.append(self.getIdFromSourceId(sourceId,'thumb'))
        
        return result
    
    def getSavedSearchCondition(self, savedSearch):
        operator = "AND"
        if savedSearch['matchtype'] == "ALL":
            operator = "AND"
        elif savedSearch['matchtype'] == "ANY":
            operator = "OR"
        elif savedSearch['matchtype'] == "NONE":
            operator = "OR"
        
        conditions = []
        conditions += self.getRatingSearchConditions(savedSearch)
        conditions += self.getMediaTypeSearchConditions(savedSearch)
        conditions += self.getFlaggedSearchConditions(savedSearch)
        conditions += self.getTextSearchConditions(savedSearch)
        conditions += self.getDateSearchConditions(savedSearch)
        
        condition = ""
        if len(conditions) > 0:
            condition += conditions[0]
            
            for i in range(1,len(conditions)):
                condition += " " + operator + " " + conditions[i]
        
        if savedSearch['matchtype'] == "NONE":
            condition = "(" + condition + ") IS FALSE"
            
        return condition
    
    def getPictureInfoForRow(self, row):
        return {'filename': row[0], 'title': row[1], 'exposure_time': row[2]}
    
    def queryPicturesMatchingCondition(self, condition):
        sql = """select filename, title, exposure_time from phototable where """ + condition + " order by exposure_time asc, filename asc"
        if condition=="":
            sql = """select filename, title, exposure_time from phototable order by exposure_time asc, filename asc"""
        self.cursor.execute(sql)
        return self.cursor
        
    def getFirstPictureMatchForCondition(self, condition):
        cursor = self.queryPicturesMatchingCondition(condition)
        row = cursor.fetchone()
        picture = None
        if row is not None:
            picture = self.getPictureInfoForRow(row)
        
        return picture
        
    def getPicturesForCondition(self, condition):
        cursor = self.queryPicturesMatchingCondition(condition)
        rows = cursor.fetchall()
        pictures = []
        for row in rows:
            pictures.append(self.getPictureInfoForRow(row))
        
        return pictures
    
    def getFirstMatchOfSavedSearch(self, savedSearch):
        return self.getFirstPictureMatchForCondition(self.getSavedSearchCondition(savedSearch))
    
    def getPicturesOfSavedSearch(self, savedSearch):
        return self.getPicturesForCondition(self.getSavedSearchCondition(savedSearch))
    
    def getPictureInfoForId(self, id):
        self.cursor.execute("""select filename, title, exposure_time from phototable where id = ? order by exposure_time asc, filename asc""", (id,))
        row = self.cursor.fetchone()
        if row is not None:
            return self.getPictureInfoForRow(row)
        else:
            return None
    
    def getEventRange(self, baseInfo):
        self.cursor.execute("""select min(exposure_time), max(exposure_time) from phototable where event_id = ?""", (baseInfo['eventid'],))
        row = self.cursor.fetchone()
        if row is None:
            return None, None
        else:
            return row[0], row[1]
    
    def getPicturesOfEvent(self, eventId, flagged = False):
        condition = 'event_id = %s'%(eventId)
        if flagged:
            condition += " AND (flags & 16) == 16"
        return self.getPicturesForCondition(condition)
    
    def getFirstPictureForEvent(self, baseInfo):
        condition = 'event_id = %s'%(baseInfo['eventid'])
        return getFirstPictureMatchForCondition(condition)
    
    def getEventInfo(self, baseInfo):
        hasResult = True
        eventInfo = baseInfo
        
        startRange, endRange = self.getEventRange(baseInfo)
        if startRange is None:
            return False, baseInfo
        
        pictureId = None
        sourceId = baseInfo['primary_source_id']
        if sourceId is not None and sourceId.startswith('thumb'):
            pictureId = self.getIdFromSourceId(sourceId, 'thumb')
        elif baseInfo['primary_photo_id'] is not None:
            pictureId = baseInfo['primary_photo_id']
        
        picture_representation = None
        if pictureId is not None:
            picture_representation = self.getPictureInfoForId(pictureId)
        
        if picture_representation is None:
            # try to get earliest picture for this event
            picture_representation = self.getFirstPictureForEvent(baseInfo)
            
        if picture_representation is None:
            return False, baseInfo
        
        eventInfo['picture_representation'] = picture_representation
        eventInfo['startrange'] = startRange
        eventInfo['endrange'] = endRange
        
        return hasResult, eventInfo
    
    def getEvents(self):
        events = []
        self.cursor.execute('select distinct id, name, primary_photo_id, primary_source_id from eventtable order by id asc')
        result = self.cursor.fetchall()
        for row in result:
            baseInfo = {
                'eventid': row[0], 
                'name': row[1], 
                'primary_photo_id': row[2], 
                'primary_source_id': row[3], 
                'picture_representation': None, 'startrange': None, 'endrange': None}
            hasResult, eventInfo = self.getEventInfo(baseInfo)
            if hasResult:
                events += [eventInfo]
        return events


if __name__ == '__main__':
    v = ShotwellAccess('/home/cello/.local/share/shotwell/data/photo.db')
    searches = v.getSavedSearches()
    print searches
    pictures = v.getPicturesOfSavedSearch(searches[5])
    print len(pictures)
    print pictures
    
