import imp
import os.path


# LOGS
def download(server, package):
    app = package.decode('utf-8')
    p = str(app)
    error = open('error.txt', 'a+')
    LOG_FILE = "Logs/download.privapp.log"
    log = imp.load_source('log', 'log.py')
    logger = log.init_logger(LOG_FILE)

    # DOWNLOAD
    if os.path.exists('Downloads/APKs/' + p + '.apk'):
        pass
    else:
        print('package: %s' % p)
        fl = server.download(p)
        det = server.details(p)
        if det is not None:
            vc = det['versionCode']
        else:
            vc = '00'
        if fl is not None:
            with open('Downloads/APKs/' + p + '/' + vc + '.apk', 'wb') as apk_file:
                for chunk in fl.get('file').get('data'):
                    apk_file.write(chunk)
                print('\nDownload successful \n')
                logger.info("Successful APK download", extra={'apk': p})
        else:
            if server.error == "Can't install. Please try again later.":
                error.write(p + os.linesep)
            logger.error("Google Play Download failure", extra={'apk': p, 'error': server.error})
    error.close()
