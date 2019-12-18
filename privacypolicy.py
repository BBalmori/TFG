import shutil
import urllib3
import imp
import os.path


def downloadPolicy(server, package):
    url = ''
    app = package.decode('utf-8')
    p = str(app)
    LOG_FILE = "Logs/download.privapp.log"
    log = imp.load_source('log', 'log.py')
    logger = log.init_logger(LOG_FILE)
    if os.path.exists('Downloads/PP/' + p + '.txt'):
        pass
    else:
        print('package: %s' % p)
        details = server.details(p)
        if details is not None:
            print('privacyPolicyUrl: %s' % server.privacyPolicyUrl)
            url = server.privacyPolicyUrl
            c = urllib3.PoolManager()
            filename = 'Downloads/PP/' + p + '.txt'
            try:
                with c.request('GET', url, preload_content=False) as res, open(filename, 'wb') as out_file:
                    shutil.copyfileobj(res, out_file)
                logger.info("Successful Privacy Policy download", extra={'app': p})
            except Exception:
                logger.error("PP Download failure", extra={'app': p, 'error': server.error})
        else:
            print(server.error)
            logger.error("PP Download failure", extra={'app': p, 'error': server.error})

