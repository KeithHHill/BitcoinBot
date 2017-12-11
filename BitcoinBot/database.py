
import ConfigParser
import MySQLdb as mdb
import os

path = os.path.dirname(os.path.abspath(__file__))

class Database():
    con = None
    cur = None
    
    def __init__(self):
        self.getCursor()
        
    def getCursor(self):
        config = ConfigParser.ConfigParser()
        config.read(path + "/config.ini")
        host = config.get('database', 'host')
        user = config.get('database', 'user')
        passwd = config.get('database', 'passwd')
        schema = config.get('database', 'schema')
        
    
    
        self.con = mdb.connect(host=host, user=user, passwd=passwd, db=schema, charset='utf8', use_unicode=True)
        self.con.autocommit(True)
        self.cur = self.con.cursor(mdb.cursors.DictCursor)
        
        return self.cur

    def execute(self, sql, args=None):
        try:
            self.runSql(sql, args)
        except (AttributeError, mdb.OperationalError):
            self.getCursor() #re-establish connection on failed query
            self.runSql(sql, args)
        
        return self.cur.lastrowid
        
    def runSql(self, sql, args):
        if args != None :
            self.cur.execute(sql, args)
        else:
            self.cur.execute(sql)
        
    def fetchAll(self, sql, args=None):
        self.execute(sql, args)
        return self.cur.fetchall()
        
    def close(self):
        if self.cur != None:
            self.cur.close()
        if self.con != None:
            self.con.close()