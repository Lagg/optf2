## About

OPTF2 is a project that started out as a humble TF2 backpack viewer, but since
then its scope has expanded towards a full Steam information display tool. From
inventories to schemas and more.

As of **8/30/2019** this repo is considered archived. At this point in time it might serve well as a historical artifact of what it was like working with the Steam API and items before the inventory system was normalized and OPTF2 no longer needed to exist. Otherwise it's rather outdated python2 code that uses the Web.Py framework. Itself something that people often have issues with.

## INSTALLATION

* Run `pip install -r requirements.txt` (Note: pylibmc requires libmemcached)
* Run `python dispatch.py` for local usage or via wsgi on your server of choice (use dispatch as the entry module)
