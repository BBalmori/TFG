#!/usr/bin/python
import imp
import sys

from Crypto.Util import asn1
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA
from Crypto.Cipher import PKCS1_OAEP

import os
import io
import logging
import requests
from base64 import b64decode, urlsafe_b64encode
from datetime import datetime

from . import googleplay_pb2, config, utils

ssl_verify = True

BASE = "https://android.clients.google.com/"
FDFE = BASE + "fdfe/"
CHECKIN_URL = BASE + "checkin"
AUTH_URL = BASE + "auth"

UPLOAD_URL = FDFE + "uploadDeviceConfig"
SEARCH_URL = FDFE + "search"
DETAILS_URL = FDFE + "details"
HOME_URL = FDFE + "homeV2"
BROWSE_URL = FDFE + "browse"
DELIVERY_URL = FDFE + "delivery"
PURCHASE_URL = FDFE + "purchase"
SEARCH_SUGGEST_URL = FDFE + "searchSuggest"
BULK_URL = FDFE + "bulkDetails"
LOG_URL = FDFE + "log"
TOC_URL = FDFE + "toc"
LIST_URL = FDFE + "list"
REVIEWS_URL = FDFE + "rev"

CONTENT_TYPE_URLENC = "application/x-www-form-urlencoded; charset=UTF-8"
CONTENT_TYPE_PROTO = "application/x-protobuf"
error = " "
policyPrivacyUrl = " "


class LoginError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class RequestError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


config_cred = None


class GooglePlayAPI(object):
    """Google Play Unofficial API Class

    Usual APIs methods are login(), search(), details(), bulkDetails(),
    download(), browse(), reviews() and list()."""

    def __init__(self, locale, timezone, device_codename='redmi',
                 proxies_config=None):
        self.authSubToken = None
        self.gsfId = None
        self.device_config_token = None
        self.proxies_config = proxies_config
        self.deviceBuilder = config.DeviceBuilder(device_codename)
        self.set_locale(locale)
        self.set_timezone(timezone)
        self.error = None
        self.privacyPolicyUrl = None

    def read_config(config_file="config_cred.py"):
        """
        Read the repository config

        The config is read from config_file, which is in the current directory.
        """
        global config_cred

        if config_cred is not None:
            return config_cred
        if not os.path.isfile(config_file):
            logging.critical("Missing config file.")
            sys.exit(2)

        config_cred = dict()

        logging.debug("Reading %s" % config_file)
        with io.open(config_file, "rb") as f:
            code = compile(f.read(), "config_cred.py", "exec")
            exec(code, None, config_cred)

        return config_cred

    def set_locale(self, locale):
        self.deviceBuilder.set_locale(locale)

    def set_timezone(self, timezone):
        self.deviceBuilder.set_timezone(timezone)

    def encrypt_password(self, login, passwd):
        """Encrypt the password using the google publickey, using
        the RSA encryption algorithm"""

        binaryKey = b64decode(config.GOOGLE_PUBKEY)
        i = utils.readInt(binaryKey, 0)
        modulus = utils.toBigInt(binaryKey[4:][0:i])
        j = utils.readInt(binaryKey, i + 4)
        exponent = utils.toBigInt(binaryKey[i + 8:][0:j])

        seq = asn1.DerSequence()
        seq.append(modulus)
        seq.append(exponent)

        publicKey = RSA.importKey(seq.encode())
        cipher = PKCS1_OAEP.new(publicKey)
        combined = login.encode() + b'\x00' + passwd.encode()
        encrypted = cipher.encrypt(combined)
        h = b'\x00' + SHA.new(binaryKey).digest()[0:4]
        return urlsafe_b64encode(h + encrypted)

    def setAuthSubToken(self, authSubToken):
        self.authSubToken = authSubToken

    def getHeaders(self, upload_fields=False):
        """Return the default set of request headers, which
        can later be expanded, based on the request type"""

        if upload_fields:
            headers = self.deviceBuilder.getDeviceUploadHeaders()
        else:
            headers = self.deviceBuilder.getBaseHeaders()
        if self.gsfId is not None:
            headers["X-DFE-Device-Id"] = "%s" % "{0:x}".format(self.gsfId)  # self.gsfId
        if self.authSubToken is not None:
            headers["Authorization"] = "GoogleLogin auth=%s" % self.authSubToken
        if self.device_config_token is not None:
            headers["X-DFE-Device-Config-Token"] = self.device_config_token
        return headers

    def checkin(self, email, ac2dmToken):
        headers = self.getHeaders()
        headers["Content-Type"] = CONTENT_TYPE_PROTO

        request = self.deviceBuilder.getAndroidCheckinRequest()

        stringRequest = request.SerializeToString()
        res = requests.post(CHECKIN_URL, data=stringRequest,
                            headers=headers, verify=ssl_verify,
                            proxies=self.proxies_config)
        response = googleplay_pb2.AndroidCheckinResponse()
        response.ParseFromString(res.content)

        # checkin again to upload gfsid
        request.id = response.androidId
        request.securityToken = response.securityToken
        request.accountCookie.append("[" + email + "]")
        request.accountCookie.append(ac2dmToken)
        stringRequest = request.SerializeToString()
        requests.post(CHECKIN_URL,
                      data=stringRequest,
                      headers=headers,
                      verify=ssl_verify,
                      proxies=self.proxies_config)

        return response.androidId

    def uploadDeviceConfig(self):
        """Upload the device configuration of the fake device
        selected in the __init__ methodi to the google account."""

        upload = googleplay_pb2.UploadDeviceConfigRequest()
        upload.deviceConfiguration.CopyFrom(self.deviceBuilder.getDeviceConfig())
        headers = self.getHeaders(upload_fields=True)
        stringRequest = upload.SerializeToString()
        response = requests.post(UPLOAD_URL, data=stringRequest,
                                 headers=headers,
                                 verify=ssl_verify,
                                 timeout=60,
                                 proxies=self.proxies_config)
        response = googleplay_pb2.ResponseWrapper.FromString(response.content)
        try:
            if response.payload.HasField('uploadDeviceConfigResponse'):
                self.device_config_token = response.payload.uploadDeviceConfigResponse
                self.device_config_token = self.device_config_token.uploadDeviceConfigToken
        except ValueError:
            pass

    def login(self, email=None, password=None, gsfId=None, authSubToken=None):
        """Login to your Google Account.
        For first time login you should provide:
            * email
            * password
        For the following logins you need to provide:
            * gsfId
            * authSubToken"""
        if email is not None and password is not None:
            # First time setup, where we obtain an ac2dm token and
            # upload device information

            encryptedPass = self.encrypt_password(email, password).decode('utf-8')
            # AC2DM token
            params = self.deviceBuilder.getLoginParams(email, encryptedPass)
            params['service'] = 'ac2dm'
            params['add_account'] = '1'
            params['callerPkg'] = 'com.google.android.gms'
            headers = self.deviceBuilder.getAuthHeaders(self.gsfId)
            headers['app'] = 'com.google.android.gsm'
            response = requests.post(AUTH_URL, data=params, verify=ssl_verify,
                                     proxies=self.proxies_config)
            data = response.text.split()
            params = {}
            for d in data:
                if "=" not in d:
                    continue
                k, v = d.split("=", 1)
                params[k.strip().lower()] = v.strip()
            if "auth" in params:
                ac2dmToken = params["auth"]
            elif "error" in params:
                if "NeedsBrowser" in params["error"]:
                    raise LoginError("Security check is needed, try to visit "
                                     "https://accounts.google.com/b/0/DisplayUnlockCaptcha "
                                     "to unlock, or setup an app-specific password")
                raise LoginError("server says: " + params["error"])
            else:
                raise LoginError("Auth token not found.")

            self.gsfId = self.checkin(email, ac2dmToken)
            self.getAuthSubToken(email, encryptedPass)
            self.uploadDeviceConfig()
        elif gsfId is not None and authSubToken is not None:
            # no need to initialize API
            self.gsfId = gsfId
            self.setAuthSubToken(authSubToken)
            # check if token is valid with a simple search
            # self.search('firefox', 1, None)
        else:
            raise LoginError('Either (email,pass) or (gsfId, authSubToken) is needed')

    def getAuthSubToken(self, email, passwd):
        requestParams = self.deviceBuilder.getLoginParams(email, passwd)
        requestParams['service'] = 'androidmarket'
        requestParams['app'] = 'com.android.vending'
        headers = self.deviceBuilder.getAuthHeaders(self.gsfId)
        headers['app'] = 'com.android.vending'
        response = requests.post(AUTH_URL,
                                 data=requestParams,
                                 verify=ssl_verify,
                                 headers=headers,
                                 proxies=self.proxies_config)
        data = response.text.split()
        params = {}
        for d in data:
            if "=" not in d:
                continue
            k, v = d.split("=", 1)
            params[k.strip().lower()] = v.strip()
        if "token" in params:
            master_token = params["token"]
            second_round_token = self.getSecondRoundToken(master_token, requestParams)
            self.setAuthSubToken(second_round_token)
        elif "error" in params:
            raise LoginError("server says: " + params["error"])
        else:
            raise LoginError("auth token not found.")

    def getSecondRoundToken(self, first_token, params):
        if self.gsfId is not None:
            params['androidId'] = "{0:x}".format(self.gsfId)
        params['Token'] = first_token
        params['check_email'] = '1'
        params['token_request_options'] = 'CAA4AQ=='
        params['system_partition'] = '1'
        params['_opt_is_called_from_account_manager'] = '1'
        params.pop('Email')
        params.pop('EncryptedPasswd')
        headers = self.deviceBuilder.getAuthHeaders(self.gsfId)
        headers['app'] = 'com.android.vending'
        response = requests.post(AUTH_URL,
                                 data=params,
                                 headers=headers,
                                 verify=ssl_verify,
                                 proxies=self.proxies_config)
        data = response.text.split()
        params = {}
        for d in data:
            if "=" not in d:
                continue
            k, v = d.split("=", 1)
            params[k.strip().lower()] = v.strip()
        if "auth" in params:
            return params["auth"]
        elif "error" in params:
            raise LoginError("server says: " + params["error"])
        else:
            raise LoginError("Auth token not found.")

    def executeRequestApi2(self, path, post_data=None, content_type=CONTENT_TYPE_URLENC, params=None):
        if self.authSubToken is None:
            raise Exception("You need to login before executing any request")
        headers = self.getHeaders()
        headers["Content-Type"] = content_type

        if post_data is not None:
            response = requests.post(path,
                                     data=str(post_data),
                                     headers=headers,
                                     params=params,
                                     verify=ssl_verify,
                                     timeout=60,
                                     proxies=self.proxies_config)
        else:
            response = requests.get(path,
                                    headers=headers,
                                    params=params,
                                    verify=ssl_verify,
                                    timeout=60,
                                    proxies=self.proxies_config)

        message = googleplay_pb2.ResponseWrapper.FromString(response.content)  ##aqui pasa algo en los metadatos
        if message.commands.displayErrorMessage != "":
            self.error = message.commands.displayErrorMessage
            return
            # raise RequestError(message.commands.displayErrorMessage)
        return message

    def searchSuggest(self, query):
        params = {"c": "3",
                  "q": requests.utils.quote(query),
                  "ssis": "120",
                  "sst": "2"}
        data = self.executeRequestApi2(SEARCH_SUGGEST_URL, params=params)
        response = data.payload.searchSuggestResponse
        return [{"type": e.type,
                 "suggestedQuery": e.suggestedQuery,
                 "title": e.title} for e in response.entry]

    def search(self, query, nb_result, offset=None):
        """ Search the play store for an app.

        nb_result is the maximum number of result to be returned.

        offset is used to take result starting from an index.
        """
        if self.authSubToken is None:
            raise Exception("You need to login before executing any request")

        remaining = nb_result
        output = []

        nextPath = SEARCH_URL + "?c=3&q={}".format(requests.utils.quote(query))
        if (offset is not None):
            nextPath += "&o={}".format(offset)
        while remaining > 0 and nextPath is not None:
            currentPath = nextPath
            data = self.executeRequestApi2(currentPath)
            if utils.hasPrefetch(data):
                response = data.preFetch[0].response
            else:
                response = data
            if utils.hasSearchResponse(response.payload):
                # we still need to fetch the first page, so go to
                # next loop iteration without decrementing counter
                nextPath = FDFE + response.payload.searchResponse.nextPageUrl
                continue
            if utils.hasListResponse(response.payload):
                cluster = response.payload.listResponse.cluster
                if len(cluster) == 0:
                    # unexpected behaviour, probably due to expired token
                    raise LoginError('Unexpected behaviour, probably expired '
                                     'token')
                cluster = cluster[0]
                if len(cluster.doc) == 0:
                    break
                if cluster.doc[0].containerMetadata.nextPageUrl != "":
                    nextPath = FDFE + cluster.doc[0].containerMetadata.nextPageUrl
                else:
                    nextPath = None
                apps = []
                for doc in cluster.doc:
                    apps.extend(doc.child)
                output += list(map(utils.fromDocToDictionary, apps))
                remaining -= len(apps)

        if len(output) > nb_result:
            output = output[:nb_result]

        return output

    def details(self, packageName):
        """Get app details from a package name.

        packageName is the app unique ID (usually starting with 'com.')."""
        path = DETAILS_URL + "?doc={}".format(requests.utils.quote(packageName))
        data = self.executeRequestApi2(path)
        try:
            self.privacyPolicyUrl = data.payload.detailsResponse.docV2.relatedLinks.privacyPolicyUrl
            if self.privacyPolicyUrl is "":
                self.error = "No privacy policy URL"
                return
            else:
                self.error = ""
        except AttributeError:
            return
        return utils.fromDocToDictionary(data.payload.detailsResponse.docV2)

    def bulkDetails(self, packageNames):
        """Get several apps details from a list of package names.

        This is much more efficient than calling N times details() since it
        requires only one request. If an item is not found it returns an empty object
        instead of throwing a RequestError('Item not found') like the details() function

        Args:
            packageNames (list): a list of app IDs (usually starting with 'com.').

        Returns:
            a list of dictionaries containing docv2 data, or None
            if the app doesn't exist"""

        params = {'au': '1'}
        req = googleplay_pb2.BulkDetailsRequest()
        req.docid.extend(packageNames)
        data = req.SerializeToString()
        message = self.executeRequestApi2(BULK_URL,
                                          post_data=data.decode("utf-8"),
                                          content_type=CONTENT_TYPE_PROTO,
                                          params=params)
        response = message.payload.bulkDetailsResponse
        return [None if not utils.hasDoc(entry) else
                utils.fromDocToDictionary(entry.doc)
                for entry in response.entry]

    def getHomeApps(self):
        path = HOME_URL + "?c=3&nocache_isui=true"
        data = self.executeRequestApi2(path)
        output = []
        cluster = data.preFetch[0].response.payload.listResponse.cluster[0]
        for doc in cluster.doc:
            output.append({"categoryId": doc.docid,
                           "categoryStr": doc.title,
                           "apps": [utils.fromDocToDictionary(c) for c in doc.child]})
        return output

    def browse(self, cat=None, subCat=None):
        """Browse categories. If neither cat nor subcat are specified,
        return a list of categories, otherwise it return a list of apps
        using cat (category ID) and subCat (subcategory ID) as filters."""
        path = BROWSE_URL + "?c=3"
        if cat is not None:
            path += "&cat={}".format(requests.utils.quote(cat))
        if subCat is not None:
            path += "&ctr={}".format(requests.utils.quote(subCat))
        data = self.executeRequestApi2(path)

        if cat is None and subCat is None:
            # result contains all categories available
            return [{'name': c.name,
                     'dataUrl': c.dataUrl,
                     'catId': c.unknownCategoryContainer.categoryIdContainer.categoryId}
                    for c in data.payload.browseResponse.category]

        output = []
        clusters = []

        if utils.hasPrefetch(data):
            for pf in data.preFetch:
                clusters.extend(pf.response.payload.listResponse.cluster)

        # result contains apps of a specific category
        # organized by sections
        for cluster in clusters:
            for doc in cluster.doc:
                apps = [a for a in doc.child]
                apps = list(map(utils.fromDocToDictionary,
                                apps))
                section = {'title': doc.title,
                           'docid': doc.docid,
                           'apps': apps}
                output.append(section)
        return output

    def list(self, cat, ctr=None, nb_results=None, offset=None):
        """List apps for a specfic category *cat*.

        If ctr (subcategory ID) is None, returns a list of valid subcategories.

        If ctr is provided, list apps within this subcategory."""
        path = LIST_URL + "?c=3&cat={}".format(requests.utils.quote(cat))
        if ctr is not None:
            path += "&ctr={}".format(requests.utils.quote(ctr))
        if nb_results is not None:
            path += "&n={}".format(requests.utils.quote(nb_results))
        if offset is not None:
            path += "&o={}".format(requests.utils.quote(offset))
        data = self.executeRequestApi2(path)
        clusters = []
        docs = []
        if ctr is None:
            # list subcategories
            for pf in data.preFetch:
                clusters.extend(pf.response.payload.listResponse.cluster)
            for c in clusters:
                docs.extend(c.doc)
            return [d.docid for d in docs]
        else:
            childs = []
            clusters.extend(data.payload.listResponse.cluster)
            for c in clusters:
                docs.extend(c.doc)
            for d in docs:
                childs.extend(d.child)
            return [utils.fromDocToDictionary(c)
                    for c in childs]

    def listApps(self, cat, ctr, nb_result, offset=None):
        """List apps for a specfic category *cat*.

        If ctr (subcategory ID) is None, returns a list of valid subcategories.

        If ctr is provided, list apps within this subcategory."""
        count = nb_result
        out = []
        nextPath = LIST_URL + "?c=3&cat={}".format(requests.utils.quote(cat))
        if ctr is not None:
            nextPath += "&ctr={}".format(requests.utils.quote(ctr))
        #if nb_result is not None:
         #   nextPath += "&n={}".format(requests.utils.quote(nb_result))
        if offset is not None:
            nextPath += "&o={}".format(requests.utils.quote(offset))
        while count > 0 and nextPath is not None:
            path = nextPath
            data = self.executeRequestApi2(path)
            if utils.hasPrefetch(data):
                response = data.preFetch[0].response
            else:
                response = data
            if utils.hasSearchResponse(response.payload):
                # we still need to fetch the first page, so go to
                # next loop iteration without decrementing counter
                nextPath = FDFE + response.payload.searchResponse.nextPageUrl
                continue
            if utils.hasListResponse(response.payload):
                cluster = response.payload.listResponse.cluster
                if len(cluster) == 0:
                    # unexpected behaviour, probably due to expired token
                    raise LoginError('Unexpected behaviour, probably expired token')
                cluster = cluster[0]
                if len(cluster.doc) == 0:
                    break
                if cluster.doc[0].containerMetadata.nextPageUrl != "":
                    nextPath = FDFE + cluster.doc[0].containerMetadata.nextPageUrl
                else:
                    nextPath = None
                apps = []
                for doc in cluster.doc:
                    apps.extend(doc.child)
                out += list(map(utils.fromDocToDictionary, apps))
                count -= len(apps)
        return out

    def reviews(self, packageName, filterByDevice=False, sort=2,
                nb_results=None, offset=None):
        """Browse reviews for an application

        Args:
            packageName (str): app unique ID.
            filterByDevice (bool): filter results for current device
            sort (int): sorting criteria (values are unknown)
            nb_results (int): max number of reviews to return
            offset (int): return reviews starting from an offset value

        Returns:
            dict object containing all the protobuf data returned from
            the api
        """
        path = REVIEWS_URL + "?doc={}&sort={}".format(requests.utils.quote(packageName), sort)
        if nb_results is not None:
            path += "&n={}".format(nb_results)
        if offset is not None:
            path += "&o={}".format(offset)
        if filterByDevice:
            path += "&dfil=1"
        data = self.executeRequestApi2(path)
        output = []
        for rev in data.payload.reviewResponse.getResponse.review:
            author = {'personIdString': rev.author2.personIdString,
                      'personId': rev.author2.personId,
                      'name': rev.author2.name,
                      'profilePicUrl': rev.author2.urls.url,
                      'googlePlusUrl': rev.author2.googlePlusUrl}
            review = {'documentVersion': rev.documentVersion,
                      'timestampMsec': rev.timestampMsec,
                      'starRating': rev.starRating,
                      'comment': rev.comment,
                      'commentId': rev.commentId,
                      'author': author}
            output.append(review)
        return output

    def _deliver_data(self, url, cookies):
        headers = self.getHeaders()
        response = requests.get(url, headers=headers,
                                cookies=cookies, verify=ssl_verify,
                                stream=True, timeout=60,
                                proxies=self.proxies_config)
        total_size = response.headers.get('content-length')
        chunk_size = 32 * (1 << 10)
        return {'data': response.iter_content(chunk_size=chunk_size),
                'total_size': total_size,
                'chunk_size': chunk_size}

    def delivery(self, packageName, versionCode=None, offerType=1,
                 downloadToken=None, expansion_files=False):
        """Download an already purchased app.

        Args:
            packageName (str): app unique ID (usually starting with 'com.')
            versionCode (int): version to download
            offerType (int): different type of downloads (mostly unused for apks)
            downloadToken (str): download token returned by 'purchase' API
            progress_bar (bool): wether or not to print a progress bar to stdout

        Returns:
            Dictionary containing apk data and a list of expansion files. As stated
            in android documentation, there can be at most 2 expansion files, one with
            main content, and one for patching the main content. Their names should
            follow this format:

            [main|patch].<expansion-version>.<package-name>.obb

            Data to build this name string is provided in the dict object. For more
            info check https://developer.android.com/google/play/expansion-files.html
        """

        if versionCode is None:
            # pick up latest version

            versionCode = self.details(packageName).get('versionCode')

        params = {'ot': str(offerType),
                  'doc': packageName,
                  'vc': str(versionCode)}
        headers = self.getHeaders()
        if downloadToken is not None:
            params['dtok'] = downloadToken
        response = requests.get(DELIVERY_URL, headers=headers,
                                params=params, verify=ssl_verify,
                                timeout=60,
                                proxies=self.proxies_config)
        response = googleplay_pb2.ResponseWrapper.FromString(response.content)
        if response.commands.displayErrorMessage != "":
            raise RequestError(response.commands.displayErrorMessage)
        elif response.payload.deliveryResponse.appDeliveryData.downloadUrl == "":
            raise RequestError('App not purchased')
        else:
            result = {}
            result['docId'] = packageName
            result['additionalData'] = []
            downloadUrl = response.payload.deliveryResponse.appDeliveryData.downloadUrl
            cookie = response.payload.deliveryResponse.appDeliveryData.downloadAuthCookie[0]
            cookies = {
                str(cookie.name): str(cookie.value)
            }
            result['file'] = self._deliver_data(downloadUrl, cookies)
            if not expansion_files:
                return result
            for obb in response.payload.deliveryResponse.appDeliveryData.additionalFile:
                a = {}
                # fileType == 0 -> main
                # fileType == 1 -> patch
                if obb.fileType == 0:
                    obbType = 'main'
                else:
                    obbType = 'patch'
                a['type'] = obbType
                a['versionCode'] = obb.versionCode
                a['file'] = self._deliver_data(obb.downloadUrl, None)
                result['additionalData'].append(a)
            return result

    def download(self, packageName, versionCode=None, offerType=1, expansion_files=False):
        """Download an app and return its raw data (APK file). Free apps need
        to be "purchased" first, in order to retrieve the download cookie.
        If you want to download an already purchased app, use *delivery* method.

        Args:
            packageName (str): app unique ID (usually starting with 'com.')
            versionCode (int): version to download
            offerType (int): different type of downloads (mostly unused for apks)
            downloadToken (str): download token returned by 'purchase' API
            progress_bar (bool): wether or not to print a progress bar to stdout

        Returns
            Dictionary containing apk data and optional expansion files
            (see *delivery*)
        """

        if self.authSubToken is None:
            raise Exception("You need to login before executing any request")

        if versionCode is None:
            # pick up latest version
            if self.details(packageName) is not None:
                versionCode = self.details(packageName).get('versionCode')
            else:
                self.error = "No versionCode"
                return

        headers = self.getHeaders()
        params = {'ot': str(offerType),
                  'doc': packageName,
                  'vc': str(versionCode)}
        self.log(packageName)
        response = requests.post(PURCHASE_URL, headers=headers,
                                 params=params, verify=ssl_verify,
                                 timeout=60,
                                 proxies=self.proxies_config)

        response = googleplay_pb2.ResponseWrapper.FromString(response.content)
        if response.commands.displayErrorMessage != "":
            self.error = response.commands.displayErrorMessage
            return
            # raise RequestError(response.commands.displayErrorMessage)
        else:
            dlToken = response.payload.buyResponse.downloadToken
            return self.delivery(packageName, versionCode, offerType, dlToken,
                                 expansion_files=expansion_files)

    def log(self, docid):
        log_request = googleplay_pb2.LogRequest()
        log_request.downloadConfirmationQuery = "confirmFreeDownload?doc=" + docid
        timestamp = int((datetime.now() - datetime.fromtimestamp(0)).total_seconds())
        log_request.timestamp = timestamp

        string_request = log_request.SerializeToString()
        response = requests.post(LOG_URL,
                                 data=string_request,
                                 headers=self.getHeaders(),
                                 verify=ssl_verify,
                                 timeout=60,
                                 proxies=self.proxies_config)
        response = googleplay_pb2.ResponseWrapper.FromString(response.content)
        if response.commands.displayErrorMessage != "":
            raise RequestError(response.commands.displayErrorMessage)

    @staticmethod
    def getDevicesCodenames():
        return config.getDevicesCodenames()

    @staticmethod
    def getDevicesReadableNames():
        return config.getDevicesReadableNames()
