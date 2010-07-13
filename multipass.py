import base64
import hashlib
import urllib
import operator
import array
from django.utils import simplejson
try:
    from Crypto.Cipher import AES
except ImportError:
    # Just pass through in dev mode
    class AES:
        MODE_CBC = 0
        new = classmethod(lambda k,x,y,z: AES)
        encrypt = classmethod(lambda k,x: x)
        decrypt = classmethod(lambda k,x: x)

#message = {
#  "guid" : "<%= example_user[:guid] %>"
#  "expires" : "<%= example_user[:expires].to_s(:db) %>",
#  "display_name" : "<%= example_user[:display_name] %>",
#  "email" : "<%= example_user[:email] %>",
#  "url" : "<%= example_user[:url] %>",
#  "avatar_url" : "<%= example_user[:avatar_url] %>"
#}
def token(message):
    block_size = 16
    mode = AES.MODE_CBC
    
    api_key = "ec6c2d980724dfcd4e408e58f063fc376f13c8a896f506204c598faf2bc2f5c1c098b928e2e87cc22d373eee0893277314bb8253269176b6fb933bffda01db2e"
    account_key = 'hackerdojo'
    iv = "OpenSSL for Ruby"
    
    json = simplejson.dumps(message, separators=(',',':'))
    
    salted = api_key+account_key
    saltedHash = hashlib.sha1(salted).digest()[:16]
    
    json_bytes = array.array('b', json[0 : len(json)]) 
    iv_bytes = array.array('b', iv[0 : len(iv)])
    
    # # xor the iv into the first 16 bytes.
    for i in range(0, 16):
    	json_bytes[i] = operator.xor(json_bytes[i], iv_bytes[i])
    
    pad = block_size - len(json_bytes.tostring()) % block_size
    data = json_bytes.tostring() + pad * chr(pad)
    aes = AES.new(saltedHash, mode, iv)
    encrypted_bytes = aes.encrypt(data)
    
    return base64.b64encode(encrypted_bytes)