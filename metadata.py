import imp
import pymysql


def metadata(server, package):
    app = package.decode('utf-8')
    p = str(app)
    # LOGS
    LOG_FILE = "Logs/details.privapp.log"
    log = imp.load_source('log', 'log.py')
    logger = log.init_logger(LOG_FILE)

    # CREO UNA CONEXION
    conn = pymysql.connect(host="localhost",
                           user="bbalmori",
                           password="Balmori",
                           database="metadatos"
                           )
    cursor = conn.cursor()

    details = server.details(p)
    if details is not None:
        package = details['docId']
        title = details['title']
        author = details['author']
        rc = details['recentChanges']
        vc = details['versionCode']
        vs = details['versionString']
        installS = details['installationSize']
        nd = details['numDownloads']
        ud = details['uploadDate']
        ads = details['containsAds']
        rat = details['aggregateRating']
        cat = details['category']
        try:
            pp = server.privacyPolicyUrl
        except AttributeError:
            pp = "No privacy policy url"

        # App TABLE
        data1 = (package, title, author, rc, vc, vs, installS, nd, ud, ads, rat['ratingsCount'], rat['starRating'],
                 rat['type'], rat['oneStarRatings'], rat['twoStarRatings'], rat['threeStarRatings'],
                 rat['fourStarRatings'], rat['fiveStarRatings'], rat['commentCount'], cat['appType'],
                 cat['appCategory'], pp)
        sql1 = "INSERT INTO App(docId, title, author, recentChanges, versionCode, versionString, installationSize, " \
               "numDownloads, uploadDate, ads, ratingsCount, starRating, ratingType, oneStarRatings, twoStarRatings, " \
               "threeStarRatings, fourStarRatings, fiveStarRatings, commentCount, appType, appCategory," \
               " privacyPolicyUrl) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, " \
               "%s, %s, %s, %s)"
        try:
            cursor.execute(sql1, data1)  # Execute the SQL command
            conn.commit()  # Commit your changes in the database
            print('1 OK')
            logger.info("Successful download table App", extra={'app': p})
        except:
            conn.rollback()  # Rollback in case there is any error
            print('NO OK 1 %s' % package)
            logger.error("Download failure table App", extra={'app': p})

        # Offers TABLE
        for o in details['offer']:
            micros = o['micros']
            cc = o['currencyCode']
            fa = o['formattedAmount']
            cf = o['checkoutFlowRequired']
            ot = o['offerType']
            se = o['saleEnds']
            data2 = (micros, cc, fa, cf, ot, se, package)
            sql2 = "INSERT INTO Offers(micros, currencyCode, formattedAmount, checkoutFlowRequired, offerType, " \
                   "saleEnds, app) VALUES (%s, %s, %s, %s, %s, %s, %s)"
            try:
                cursor.execute(sql2, data2)  # Execute the SQL command
                conn.commit()  # Commit your changes in the database
                print('2 OK')
                logger.info("Successful download table Offers", extra={'app': p})
            except:
                conn.rollback()  # Rollback in case there is any error
                print('NO OK 2 %s' % package)
                logger.error("Download failure table Offers", extra={'app': p})

            # Dependencies TABLE
            for d in details['dependencies']:
                pn = d['packageName']
                v = d['version']
                data3 = (pn, v, package)  # dependencies
                sql3 = "INSERT INTO Dependencies(packageName, version, app) " \
                       "VALUES (%s, %s, %s)"
                try:
                    cursor.execute(sql3, data3)
                    conn.commit()  # Commit your changes in the database
                    print('3 OK')
                    logger.info("Successful download table Dependencies", extra={'app': p})
                except:
                    conn.rollback()  # Rollback in case there is any error
                    print('NO OK 3 %s' % package)
                    logger.error("Download failure table Dependencies", extra={'app': p})

        # Files TABLE
        for f in details['files']:
            ft = f['fileType']
            v = f['version']
            s = f['size']
            data4 = (ft, v, s, package)  # files
            sql4 = "INSERT INTO Files(fileType, version, size, app) " \
                   "VALUES (%s, %s, %s, %s)"
            try:
                cursor.execute(sql4, data4)
                conn.commit()  # Commit your changes in the database
                print('4 OK')
                logger.info("Successful download table Files", extra={'app': p})
            except:
                conn.rollback()  # Rollback in case there is any error
                print('NO OK 4 %s' % package)
                logger.error("Download failure table Files", extra={'app': p})

        # Permission TABLE
        for p in details['permission']:
            data5 = (p, package)  # permission
            sql5 = "INSERT INTO Permissions(permission, app) " \
                   "VALUES (%s, %s)"
            try:
                cursor.execute(sql5, data5)
                conn.commit()  # Commit your changes in the database
                print('5 OK')
                logger.info("Successful download table Permissions", extra={'app': p})
            except:
                conn.rollback()  # Rollback in case there is any error
                print('NO OK 5 %s' % package)
                logger.error("Download failure table Permissions", extra={'app': p})
    else:
        pass

    conn.close()