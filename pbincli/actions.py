"""Action functions for argparser"""
import json, os, ntpath, sys
import pbincli.actions
#import pbincli.sjcl_gcm
import pbincli.sjcl_simple
from pbincli.utils import PBinCLIException, check_readable, check_writable, json_load_byteified
from base64 import b64encode, b64decode
from Crypto.Hash import SHA256
from pbincli.transports import privatebin
from zlib import compress, decompress


def path_leaf(path):
    head, tail = ntpath.split(path)
    return tail or ntpath.basename(head)


def send(args):
    passphrase = os.urandom(32)
    if args.debug: print("Passphrase:\t{}".format(b64encode(passphrase)))
    if args.password:
        p = SHA256.new()
        p.update(args.password.encode("UTF-8"))
        passphrase = b64encode(passphrase + p.hexdigest().encode("UTF-8"))
    else:
        passphrase = b64encode(passphrase)
    if args.debug: print("Password:\t{}".format(passphrase))

    if args.comment:
        text = b64encode(compress(args.comment))
    else:
        text = b64encode(compress("Sending file to you!"))

    if args.file:
        check_readable(args.file)
        with open(args.file, "rb") as f:
            contents = f.read()
            f.close()

        if args.debug: print("Filename:\t{}".format(path_leaf(args.file)))
        file = b64encode(compress(contents))
        filename = b64encode(compress(path_leaf(args.file)))

        cipherfile = pbincli.sjcl_simple.encrypt(passphrase, file)
        cipherfilename = pbincli.sjcl_simple.encrypt(passphrase, filename)

    """Sending text from 'data' string"""
    #cipher = SJCL().encrypt(b64encode(text), passphrase)
    cipher = pbincli.sjcl_simple.encrypt(passphrase, text)
    request = {'data':json.dumps(cipher, ensure_ascii=False).replace(' ',''),'expire':args.expire,'formatter':args.format,'burnafterreading':int(args.burn),'opendiscussion':int(args.discus)}
    if cipherfile and cipherfilename:
        request['attachment'] = json.dumps(cipherfile, ensure_ascii=False).replace(' ','')
        request['attachmentname'] = json.dumps(cipherfilename, ensure_ascii=False).replace(' ','')

    if args.debug: print("Request:\t{}".format(request))

    result, server = privatebin().post(request)
    if args.debug: print("Response:\t{}\n".format(result.decode("UTF-8")))
    result = json.loads(result)
    """Standart response: {"status":0,"id":"aaabbb","url":"\/?aaabbb","deletetoken":"aaabbbccc"}"""
    if result['status'] == 0:
        print("Paste uploaded!\nPasteID:\t{}\nPassword:\t{}\nDelete token:\t{}\n\nLink:\t{}?{}#{}".format(result['id'], passphrase.decode("UTF-8"), result['deletetoken'], server, result['id'], passphrase.decode("UTF-8")))
    else:
        print("Something went wrong...\nError:\t{}".format(result['message']))
        sys.exit(1)


def get(args):
    paste = args.pasteinfo.split("#")
    if paste[0] and paste[1]:
        if args.debug: print("PasteID:\t{}\nPassword:\t{}\n".format(paste[0], paste[1]))
        result = privatebin().get(args.pasteinfo)
    else:
        print("PBinCLI error: Incorrect request")
        sys.exit(1)
    if args.debug: print("Response:\t{}\n".format(result.decode("UTF-8")))

    result = json.loads(result)
    if result['status'] == 0:
        print("Paste received! Text inside:")
        data = pbincli.utils.json_loads_byteified(result['data'])
        text = pbincli.sjcl_simple.decrypt(paste[1], data)
        #text = pbincli.sjcl_gcm.SJCL().decrypt(daat, paste[1])
        print(decompress(b64decode(text)))

        if 'attachment' in result and 'attachmentname' in result:
            print("Found file, attached to paste. Decoding it and saving")
            cipherfile = pbincli.utils.json_loads_byteified(result['attachment']) 
            cipherfilename = pbincli.utils.json_loads_byteified(result['attachmentname'])
            attachment = pbincli.sjcl_simple.decrypt(paste[1], cipherfile)
            attachmentname = pbincli.sjcl_simple.decrypt(paste[1], cipherfilename)
            file = decompress(b64decode(attachment))
            filename = decompress(b64decode(attachmentname))
            if args.debug: print("Filename:\t{}\n".format(filename))

            check_writable(filename)
            with open(filename, "wb") as f:
                f.write(file)
                f.close

        if 'burnafterreading' in result['meta'] and result['meta']['burnafterreading']:
            result = privatebin().delete(paste[0], 'burnafterreading')
            if args.debug: print("Delete response:\t{}\n".format(result.decode("UTF-8")))
    else:
        print("Something went wrong...\nError:\t{}".format(result['message']))
        sys.exit(1)
