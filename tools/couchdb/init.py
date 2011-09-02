# Initializes optf2's required databases and views
import sys
sys.path.append("../../")
import config

db = config.database_server

# Database view initialization
profiles = db.create_db("profiles")
profiles.save_doc(
{
   "_id": "_design/views",
   "language": "javascript",
   "views": {
       "vanity": {
           "map": "function(doc) {\n  if(doc.vanity) {\n    emit(doc.vanity, null);\n  }\n}"
       }
   }
}
, force_update = True)

viewcounts = db.create_db(config.game_mode + "_viewcounts")
viewcounts.save_doc(
{
   "_id": "_design/views",
   "language": "javascript",
   "views": {
       "counts": {
           "map": "function(doc) {\n  if (doc.c) {\n    emit(doc.c, null);\n  }\n}"
       }
   }
}
, force_update = True)

backpacks = db.create_db(config.game_mode + "_backpacks")
backpacks.save_doc(
{
   "_id": "_design/views",
   "language": "javascript",
   "views": {
       "timeline": {
           "map": "function(doc) {\n  if (doc.timestamp) {\n    emit([doc._id.split('-', 1)[0], doc.timestamp], null);\n  }\n}"
       }
   }
}
, force_update = True)

# Unpopulated dbs
dbs = ["items"]
for dbname in dbs:
    db.create_db(config.game_mode + "_" + dbname)
