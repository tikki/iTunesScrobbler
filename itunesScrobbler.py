# encoding: utf-8
"""
itunesScrobbler.py mode

scrobbles your iTunes Media Library

mode must be one of the following:

    update      reset the internal database to your iTunes Media Library
                (without sending any data to last.fm)
    scrobble    update from your iTunes Media Library and send the new
                play count data to last.fm

NOTE: You should *update* on your first run, otherwise your whole library will
      be scrobbled; you probably don't want that!
"""

# this script uses the (imho kinda ugly - sorry :F -, but very well working!)
# scrobbler lib by exhuma; get it at http://sourceforge.net/projects/scrobbler/

import sqlite3

def openDatabase(path):
    db = sqlite3.connect(path)
    try:
        db.execute('SELECT * FROM library LIMIT 0,1')
    except sqlite3.OperationalError:
        db.execute('''CREATE TABLE library (
    id text primary key,
    count integer
);''')
    return db

def updateDatabaseWithTrack(db, track):
    id = track['Persistent ID']
    count = track['Play Count'] if 'Play Count' in track else 0
    cursor = db.execute('UPDATE library SET count = ? WHERE id = ?', (count, id))
    if cursor.rowcount is 0:
        db.execute('INSERT INTO library (id, count) VALUES (?, ?)', (id, count))

def playCountDiffWithDatabaseForTrack(db, track):
    if 'Play Count' not in track:
        return 0
    trackId = track['Persistent ID']
    trackCount = track['Play Count']
    cursor = db.execute('SELECT `count` FROM library WHERE id = ?', (trackId,))
    row = cursor.fetchone()
    dbCount = 0 if row is None else row[0]
    countDiff = trackCount - dbCount
    if countDiff < 0:
        raise ValueError('Differential count for track with id `%s` is negative.' % trackId)
    return countDiff

def scrobble(track):
    artist = track['Artist']
    trackName = track['Name']
    playDate = int(mktime(track['Play Date UTC'].timetuple()))
    source = 'P'
    rating = ''
    trackLength = track.get('Total Time', 0) // 1000
    album = track.get('Album', '')
    trackNumber = track.get('Track Number', '')
    MusicBrainId = ''
    autoflush = False
    if trackLength > 30:
        print(artist, trackName, playDate, source, rating, trackLength, album, trackNumber, MusicBrainId, autoflush)
        # scrobbler.submit
        raw_input()

def main():
    import sys, os
    from time import mktime
    import plistlib

    import scrobbler

    # get modus operandi and additional arguments
    mode = None
    try:
        mode = sys.argv[1]
    except:
        pass
    if mode not in ('update', 'scrobble'):
        exit(__doc__)
        
    # load internal database
    dbPath = 'itunesScrobbler.sqlite3'
    print 'loading internal database...'
    db = openDatabase(dbPath)
    
    # load itunes media library
    print 'loading iTunes Media Library...'
    mediaLibPath = os.path.join(os.path.expanduser('~'), 'Music', 'iTunes', 'iTunes Music Library.xml')
    mediaLib = plistlib.readPlist(mediaLibPath)
    
    # if we're trying to scrobble, load username and password and try to log in
    if mode == 'scrobble':
        with open('.itunesScrobbler') as fd:
            username = fd.readline().rstrip('\r\n')
            password = fd.readline().rstrip('\r\n')
        # scrobbler.login(username, password)
        # load external scrobble list (if available)
        if listName:
            import re
            countAndId = re.compile('^(?P<count>\d+) x (?<id>[^:]+): ').search
            print 'loading supplied scrobble list...'
            with open(listName) as fd:
                for lineNr, line in enumerate(fd, 1):
                    data = countAndId(line)
                    if not data:
                        print 'error in line %i' % lineNr
                    else:
                        data = data.groupdict()
                        data['count']
                        data['id']
                    
    tracks = mediaLib['Tracks']
    for trackId, track in tracks.iteritems():
        # print trackId
        try:
            if mode == 'update':
                updateDatabaseWithTrack(db, track)
            elif mode == 'list':
                count = playCountDiffWithDatabaseForTrack(db, track)
                # for i in xrange(count):
                if count:
                    print count, ('x %(Persistent ID)s: %(Artist)s - %(Name)s' % track).encode('unicode-escape')
                    # print '%i x %r' % (, track)
            elif mode == 'scrobble':
                count = playCountDiffWithDatabaseForTrack(db, track)
                for i in xrange(count):
                    scrobble(track)
                updateDatabaseWithTrack(db, track)
        except KeyError:
            pass
    # if mode == 'scrobble':
        # scrobbler.flush()
    
    db.commit()
    db.close()

if __name__ == '__main__':
    main()
