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
import scrobbler

import sqlite3
from time import mktime

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
        return scrobbler.submit(artist, trackName, playDate, source, rating, trackLength, album, trackNumber, MusicBrainId, autoflush)
    return True

def main():
    import sys, os
    import plistlib
    import datetime

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

    # synchronize libraries
    tracks = mediaLib['Tracks']
    tracksToScrobble = []
    print 'synchronizing databases...'
    for trackId, track in tracks.iteritems():
        try:
            if mode == 'update':
                updateDatabaseWithTrack(db, track)
            # gather scrobble data
            elif mode == 'scrobble':
                count = playCountDiffWithDatabaseForTrack(db, track)
                if count:
                    tracksToScrobble.append((count, track))
        except KeyError:
            pass
    # process gathered information
    if mode == 'update':
        print 'done! - internal database updated.'
    elif mode == 'scrobble':
        if not tracksToScrobble:
            print 'done! - nothing changed; nothing to scrobble.'
        else:
            # print what we want to scrobble
            print
            print 'This is what we\'ll send to last.fm:'
            print
            for count, track in tracksToScrobble:
                print count, ('x %(Artist)s - %(Name)s' % track).encode('unicode-escape')
            print
            okay = raw_input('is this okay with you? (y/N)  ')
            if okay != 'y':
                print 'alright, let\'s forget about it.'
            else:
                # try to load username and password and log in
                with open('.itunesScrobbler') as fd:
                    username = fd.readline().rstrip('\r\n')
                    password = fd.readline().rstrip('\r\n')
                print 'trying to log in to last.fm...'
                scrobbler.login(username, password)
                # scrobble!
                print 'scrobble ...',
                for count, track in tracksToScrobble:
                    trackDescription = ('%(Name)s by %(Artist)s' % track).encode('unicode-escape')
                    if len(trackDescription) > 70:
                        trackDescription = trackDescription[:68] + '..'
                    print '\rscrobble', trackDescription,
                    for i in xrange(count):
                        # need to compensate; we only know when the track was *last* played
                        if i is 0:
                            fixedTrack = track
                        else:
                            trackLength = track.get('Total Time', 0) // 1000
                            oldPlayDate = mktime(track['Play Date UTC'].timetuple()) - i * trackLength
                            newPlayDate = oldPlayDate - i * trackLength
                            fixedTrack = track.copy()
                            fixedTrack['Play Date UTC'] = datetime.datetime.fromtimestamp(newPlayDate)
                        # send the fixed track information off to last.fm
                        if not scrobble(fixedTrack):
                            print
                            raise scrobbler.PostError('could not scrobble!')
                    updateDatabaseWithTrack(db, track)
                if not scrobbler.flush():
                    # Damn! Something went wrong right at the end.
                    # We could roll back our internal database now, which could lead to duplicate scrobbles,
                    # or we could just ignore this error, which could/will lead to tracks not being scrobbled at all;
                    # both scenarios suck donkey dick!
                    print 'b0rked hard; so sorry :f - you just lost some scrobbles due to bad caching.'
                else:
                    print 'all done! :)'
    
    db.commit()
    db.close()

if __name__ == '__main__':
    main()
