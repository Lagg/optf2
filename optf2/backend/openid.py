from optf2.backend import database
import hmac, hashlib, os, config

gsession = None

def make_hash(url):
    openid_secret = os.path.join(config.cache_file_dir, "oid_super_secret")
    if not os.path.exists(openid_secret):
        secretfile = file(openid_secret, "wb+")
        secretfile.write(os.urandom(32))
        secretfile.close()
    openid_secret = file(openid_secret, "rb").read()

    return hmac.new(openid_secret, url, hashlib.sha1).hexdigest()

def check_hash(thehash):
    strs = thehash.split(',')
    if len(strs) == 2 and strs[0] == make_hash(strs[1]):
        return True
    gsession.kill()
    return False

def get_id():
    thehash = gsession.get("identity_hash")
    if thehash and check_hash(thehash):
        hashurl = thehash.split(',')[1]
        if hashurl.endswith('/'): hashurl = hashurl[:-1]
        return database.load_profile_cached(os.path.basename(hashurl))
    return None

def set_session(session):
    global gsession
    gsession = session
