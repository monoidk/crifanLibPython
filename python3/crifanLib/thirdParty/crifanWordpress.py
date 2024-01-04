# Function: Wordpress related functions
# Author: Crifan Li
# Update: 20210922
# Latest: https://github.com/crifan/crifanLibPython/blob/master/python3/crifanLib/thirdParty/crifanWordpress.py

from datetime import datetime
import logging
import re
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

class crifanWordpress(object):
    """Use Python operate Wordpress via REST api

        Posts | REST API Handbook | WordPress Developer Resources
        https://developer.wordpress.org/rest-api/reference/posts/#schema-comment_status

        taxonomy = category / post_tag / nav_menu / link_category / post_format
            Categories | REST API Handbook | WordPress Developer Resources
            https://developer.wordpress.org/rest-api/reference/categories/

            Tags | REST API Handbook | WordPress Developer Resources
            https://developer.wordpress.org/rest-api/reference/tags/
    """

    JWT_TOKEN_VALID_CODE = "jwt_auth_valid_token"
    JWT_TOKEN_INVALID_CODE = "jwt_auth_invalid_token"

    # SearchTagPerPage = 10
    SearchTagPerPage = 100 # large enough to try response all for only sinlge call, max per_page is 100

    # RequestsTimeout = 20 # max timeout for requests. Especially for /wp-json/wp/v2/media many time will stuck so add this.

    MaxRetryNum = 10

    ################################################################################
    # Class Method
    ################################################################################

    def __init__(self, host, jwtToken, requestsProxies=None):
        self.host = host # 'https://www.crifan.org'
        self.authorization = f"Bearer {jwtToken}"
        self.requestsProxies = requestsProxies # {'http': 'http://127.0.0.1:58591', 'https': 'http://127.0.0.1:58591'}

        # "https://www.crifan.org/wp-json/jwt-auth/v1/token/validate"
        self.apiValidateToken = self.host + "/wp-json/jwt-auth/v1/token/validate"

        # https://developer.wordpress.org/rest-api/reference/media/
        self.apiMedia = self.host + "/wp-json/wp/v2/media" # 'https://www.crifan.org/wp-json/wp/v2/media'
        # https://developer.wordpress.org/rest-api/reference/posts/
        self.apiPosts = self.host + "/wp-json/wp/v2/posts" # 'https://www.crifan.org/wp-json/wp/v2/posts'
        # https://developer.wordpress.org/rest-api/reference/categories/#create-a-category
        self.apiCategories = self.host + "/wp-json/wp/v2/categories" # 'https://www.crifan.org/wp-json/wp/v2/categories'
        # https://developer.wordpress.org/rest-api/reference/tags/#create-a-tag
        self.apiTags = self.host + "/wp-json/wp/v2/tags" # 'https://www.crifan.org/wp-json/wp/v2/tags'

        # requests.adapters.DEFAULT_RETRIES = 10
        self.reqSession = requests.Session()
        self.reqRetry = Retry(connect=self.MaxRetryNum, backoff_factor=0.5)
        self.reqAdapter = HTTPAdapter(max_retries=self.reqRetry)
        self.reqSession.mount('http://', self.reqAdapter)
        self.reqSession.mount('https://', self.reqAdapter)

    def validateToken(self):
        """Validate wordpress REST api jwt token is valid or not
        Args:
        Returns:
            bool, str: True/False, None/invalid reason
        Raises:
        """
        curHeaders = {
            "Authorization": self.authorization,
            "Accept": "application/json",
        }
        validateTokenUrl = self.apiValidateToken
        # resp = requests.post(
        resp = self.reqSession.post(
            validateTokenUrl,
            proxies=self.requestsProxies,
            headers=curHeaders,
        )
        logging.debug("resp=%s", resp)
        isTokenOk, respInfo = crifanWordpress.processCommonResponse(resp)
        if isTokenOk:
            respCode = respInfo["code"]
            if respCode == crifanWordpress.JWT_TOKEN_VALID_CODE:
                isTokenOk = True
            else:
                isTokenOk = False
        return isTokenOk, respInfo

    def generateUploadedImageUrl(self, uploadImageFilename):
        """Generate uplaod image file url

        Args:
            uploadImageFilename (str): upload image filename
        Returns:
            str
        Raises:
        """
        curDatetime = datetime.now() # datetime.datetime(2021, 3, 25, 22, 42, 7, 834462)
        yearMonthStr = curDatetime.strftime(format="%Y/%m") # '2021/03'
        uploadedImageUrl = f"{self.host}/files/pic/uploads/{yearMonthStr}/{uploadImageFilename}"
        # 'https://www.crifan.org/files/pic/uploads/2021/03/f60ea32cf4664b41922431f4ea015621.jpg'
        return uploadedImageUrl

    def createMedia(self, contentType, filename, mediaBytes):
        """Create wordpress media (image)
            by call REST api: POST /wp-json/wp/v2/media

        Args:
            contentType (str): content type
            filename (str): attachment file name
            mediaBytes (bytes): media binary bytes
        Returns:
            (bool, dict)
                True, uploaded media info
                False, error detail
        Raises:
        """
        curHeaders = {
            "Authorization": self.authorization,
            "Content-Type": contentType,
            "Accept": "application/json",
            'Content-Disposition': f'attachment; filename={filename}',
        }
        logging.debug("curHeaders=%s", curHeaders)
        # curHeaders={'Authorization': 'Bearer eyJ0xxxyyy.zzzB4', 'Content-Type': 'image/png', 'Content-Disposition': 'attachment; filename=f6956c30ef0b475fa2b99c2f49622e35.png'}
        createMediaUrl = self.apiMedia
        # resp = requests.post(
        resp = self.reqSession.post(
            createMediaUrl,
            proxies=self.requestsProxies,
            headers=curHeaders,
            # timeout=self.RequestsTimeout,
            data=mediaBytes,
        )
        logging.debug("resp=%s", resp)

        isUploadOk, respInfo = crifanWordpress.processCommonResponse(resp)
        return isUploadOk, respInfo

    def createPost(self,
            title,
            content,
            dateStr,
            slug,
            categoryNameList=[],
            tagNameList=[],
            status="draft",
            postFormat="standard",
        ):
        """Create wordpress post
            by call REST api: POST /wp-json/wp/v2/posts

        Args:
            title (str): post title
            content (str): post content of html
            dateStr (str): date string
            slug (str): post slug url
            categoryNameList (list): category name list
            tagNameList (list): tag name list
            status (str): status, default to 'draft'
            postFormat (str): post format, default to 'standard'
        Returns:
            (bool, dict)
                True, uploaded post info
                False, error detail
        Raises:
        """
        curHeaders = {
            "Authorization": self.authorization,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        logging.debug("curHeaders=%s", curHeaders)

        categoryIdList = []
        tagIdList = []

        if categoryNameList:
            # ['Mac']
            categoryIdList = self.getTaxonomyIdList(categoryNameList, taxonomy="category")
            # category nameList=['Mac'] -> taxonomyIdList=[1374]

        if tagNameList:
            # ['切换', 'GPU', 'pmset', '显卡模式']
            tagIdList = self.getTaxonomyIdList(tagNameList, taxonomy="post_tag")
            # post_tag nameList=['切换', 'GPU', 'pmset', '显卡模式'] -> taxonomyIdList=[1367, 13224, 13225, 13226]

        postDict = {
            "title": title, # '【记录】Mac中用pmset设置GPU显卡切换模式'
            "content": content, # '<html>\n <div>\n  折腾：\n </div>\n <div>\n  【已解决】Mac Pro 2018款发热量大很烫非常烫\n </div>\n <div>\n  期间，...performance graphic cards\n    </li>\n   </ul>\n  </ul>\n </ul>\n <div>\n  <br/>\n </div>\n</html>'
            # "date_gmt": dateStr,
            "date": dateStr, # '2020-08-17T10:16:34'
            "slug": slug, # 'on_mac_pmset_is_used_set_gpu_graphics_card_switching_mode'
            "status": status, # 'draft'
            "format": postFormat, # 'standard'
            "categories": categoryIdList, # [1374]
            "tags": tagIdList, # [1367, 13224, 13225, 13226]
            # TODO: featured_media, excerpt
        }
        logging.debug("postDict=%s", postDict)
        # postDict={'title': '【记录】Mac中用pmset设置GPU显卡切换模式', 'content': '<html>\n <div>\n  折腾：\n </div>\n <div>\。。。。<br/>\n </div>\n</html>', 'date': '2020-08-17T10:16:34', 'slug': 'on_mac_pmset_is_used_set_gpu_graphics_card_switching_mode', 'status': 'draft', 'format': 'standard', 'categories': [1374], 'tags': [1367, 13224, 13225, 13226]}
        createPostUrl = self.apiPosts
        # resp = requests.post(
        resp = self.reqSession.post(
            createPostUrl,
            proxies=self.requestsProxies,
            headers=curHeaders,
            # data=json.dumps(postDict),
            json=postDict, # internal auto do json.dumps
        )
        logging.info("createPostUrl=%s -> resp=%s", createPostUrl, resp)

        isUploadOk, respInfo = crifanWordpress.processCommonResponse(resp)
        return isUploadOk, respInfo

    def createTaxonomy(self, name, taxonomy, parent=None, slug=None, description=None):
        """Create wordpress taxonomy(category/tag)
            by call REST api: 
                POST /wp-json/wp/v2/categories
                POST /wp-json/wp/v2/tags

        Args:
            name (str): category name
            taxonomy (str): type: category/tag
            parent (int): category parent
            slug (str): category slug
            description (str): category description
        Returns:
            (bool, dict)
                True, uploaded category info
                False, error detail
        Raises:
        """
        curHeaders = {
            "Authorization": self.authorization,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        logging.debug("curHeaders=%s", curHeaders)
        # curHeaders={'Authorization': 'Bearer eyxxx9.eyxxxfQ.5Ixxxm-6Yxxxs', 'Content-Type': 'application/json', 'Accept': 'application/json'}

        postDict = {
            "name": name, #
        }

        if slug:
            postDict["slug"] = slug

        if description:
            postDict["description"] = description

        if taxonomy == "category":
            if parent:
                postDict["parent"] = parent

        createTaxonomyUrl = ""
        if taxonomy == "category":
            createTaxonomyUrl = self.apiCategories
        elif taxonomy == "post_tag":
            createTaxonomyUrl = self.apiTags

        # resp = requests.post(
        resp = self.reqSession.post(
            createTaxonomyUrl,
            proxies=self.requestsProxies,
            headers=curHeaders,
            json=postDict,
        )
        logging.info("resp=%s for POST %s with postDict=%s", resp, createTaxonomyUrl, postDict)
        # {'id': 13223, 'count': 0, 'description': '', 'link': 'https://www.crifan.org/category/mac-2/', 'name': 'Mac', 'slug': 'mac-2', 'taxonomy': 'category', 'parent': 0, 'meta': [], '_links': {'self': [{'href': 'https://www.crifan.org/wp-json/wp/v2/categories/13223'}], 'collection': [{'href': 'https://www.crifan.org/wp-json/wp/v2/categories'}], 'about': [{'href': 'https://www.crifan.org/wp-json/wp/v2/taxonomies/category'}], 'wp:post_type': [{'href': 'https://www.crifan.org/wp-json/wp/v2/posts?categories=13223'}], 'curies': [{'name': 'wp', 'href': 'https://api.w.org/{rel}', 'templated': True}]}}
        # postDict={'name': 'Mac'}
        # postDict={'name': 'GPU'}

        isCreateOk, respInfo = crifanWordpress.processCommonResponse(resp)
        logging.debug("isCreateOk=%s, respInfo=%s", isCreateOk, respInfo)
        # isCreateOk=True, respInfo={'id': 13224, 'slug': 'gpu', 'link': 'https://www.crifan.org/tag/gpu/', 'name': 'GPU', 'description': ''}

        return isCreateOk, respInfo

    def getTaxonomySinglePage(self, name, taxonomy, curPage, perPage=None):
        """Get single page wordpress category/post_tag
            return the whole page items

            by call REST api: 
                GET /wp-json/wp/v2/categories
                GET /wp-json/wp/v2/tags

        Args:
            name (str): category name
            taxonomy (str): taxonomy type: category/post_tag
            curPage (int): current page number
            perPage (int): max items per page. Default None. If None, use SearchTagPerPage=100
        Returns:
            (bool, dict)
                True, found taxonomy info
                False, error detail
        Raises:
        """
        curHeaders = {
            "Authorization": self.authorization,
            "Accept": "application/json",
        }
        logging.debug("curHeaders=%s", curHeaders)

        if perPage is None:
            perPage = crifanWordpress.SearchTagPerPage

        queryParamDict = {
            "search": name, # 'Mac'
            "page": curPage, # 1
            "per_page": perPage, # 100
        }

        searchTaxonomyUrl = ""
        if taxonomy == "category":
            searchTaxonomyUrl = self.apiCategories
        elif taxonomy == "post_tag":
            searchTaxonomyUrl = self.apiTags

        # resp = requests.get(
        resp = self.reqSession.get(
            searchTaxonomyUrl,
            proxies=self.requestsProxies,
            headers=curHeaders,
            # data=queryDict, # {'search': 'Mac'}
            params=queryParamDict, # {'search': 'Mac'}
        )
        logging.debug("resp=%s for GET %s with para=%s", resp, searchTaxonomyUrl, queryParamDict)

        isSearchOk, respTaxonomyLit = crifanWordpress.processCommonResponse(resp)
        logging.debug("isSearchOk=%s, respTaxonomyLit=%s", isSearchOk, respTaxonomyLit)

        return isSearchOk, respTaxonomyLit

    def getAllTaxonomy(self, name, taxonomy):
        """Get all page of wordpress category/post_tag

        Args:
            name (str): category name to search
            taxonomy (str): taxonomy type: category/post_tag
        Returns:
            (bool, dict)
                True, found taxonomy info
                False, error detail
        Raises:
        """
        isGetAllOk = False
        respInfo = None

        perPage = crifanWordpress.SearchTagPerPage

        firstPageNum = 1
        isFirstPageSearchOk, firstPageRespInfo = self.getTaxonomySinglePage(name, taxonomy, firstPageNum, perPage)
        if isFirstPageSearchOk:
            isGetAllOk = True

            firstPageRespList = firstPageRespInfo
            respAllTaxonomyLit = firstPageRespList
            firstPageRespItemNum = len(firstPageRespList)
            if firstPageRespItemNum >= perPage:
                # get next page
                isRestEachPageOk = True
                isRestEachPageRespFull = True
                restCurPage = firstPageNum + 1
                restRespAllItemList = []
                while (isRestEachPageOk and isRestEachPageRespFull):
                    isRestEachPageOk, restEachPageRespItemList = self.getTaxonomySinglePage(name, taxonomy, restCurPage, perPage)
                    if isRestEachPageOk:
                        restEachPageRespItemNum = len(restEachPageRespItemList)
                        isRestEachPageRespFull = restEachPageRespItemNum >= perPage

                        restRespAllItemList.extend(restEachPageRespItemList)

                    restCurPage += 1

                respAllTaxonomyLit.extend(restRespAllItemList)

            respInfo = respAllTaxonomyLit
        else:
            isGetAllOk = False
            respInfo = firstPageRespInfo

        return isGetAllOk, respInfo

    def searchTaxonomy(self, name, taxonomy):
        """Search wordpress category/post_tag
            return the exactly matched one, name is same, or name lowercase is same

        Args:
            name (str): category name to search
            taxonomy (str): taxonomy type: category/post_tag
        Returns:
            (bool, dict)
                True, found taxonomy info
                False, error detail
        Raises:
        """
        isSearchOk = False
        finalRespTaxonomy = None

        isGetAllOk, respInfo = self.getAllTaxonomy(name, taxonomy)
        if isGetAllOk:
            isSearchOk = True
            respAllTaxonomyLit = respInfo
            finalRespTaxonomy = crifanWordpress.findSameNameTaxonomy(name, respAllTaxonomyLit)
            logging.debug("finalRespTaxonomy=%s", finalRespTaxonomy)

        return isSearchOk, finalRespTaxonomy

    def getTaxonomyIdList(self, nameList, taxonomy):
        """convert taxonomy(category/post_tag) name list to wordpress category/post_tag id list

        Args:
            nameList (list): category/post_tag name list
            taxonomy (str): the name type: category/post_tag
        Returns:
            taxonomy id list(list)
        Raises:
        """
        taxonomyIdList = []

        totalNum = len(nameList)
        for curIdx, eachTaxonomyName in enumerate(nameList):
            curNum = curIdx + 1
            logging.info("%s taxonomy [%d/%d] %s %s", "-"*10, curNum, totalNum, eachTaxonomyName, "-"*10)
            curTaxonomy = None

            isSearhOk, existedTaxonomy = self.searchTaxonomy(eachTaxonomyName, taxonomy)
            logging.debug("isSearhOk=%s, existedTaxonomy=%s", isSearhOk, existedTaxonomy)
            # isSearhOk=True, existedTaxonomy={'id': 1374, 'count': 350, 'description': '', 'link': 'https://www.crifan.org/category/work_and_job/operating_system_and_platform/mac/', 'name': 'Mac', 'slug': 'mac', 'taxonomy': 'category', 'parent': 4624, 'meta': [], '_links': {'self': [{'href': 'https://www.crifan.org/wp-json/wp/v2/categories/1374'}], 'collection': [{'href': 'https://www.crifan.org/wp-json/wp/v2/categories'}], 'about': [{'href': 'https://www.crifan.org/wp-json/wp/v2/taxonomies/category'}], 'up': [{'embeddable': True, 'href': 'https://www.crifan.org/wp-json/wp/v2/categories/4624'}], 'wp:post_type': [{'href': 'https://www.crifan.org/wp-json/wp/v2/posts?categories=1374'}], 'curies': [{'name': 'wp', 'href': 'https://api.w.org/{rel}', 'templated': True}]}}
            if isSearhOk and existedTaxonomy:
                curTaxonomy = existedTaxonomy
                logging.info("Found existed %s: name=%s,id=%s,slug=%s", taxonomy, curTaxonomy["name"], curTaxonomy["id"], curTaxonomy["slug"])
            else:
                isCreateOk, createdTaxonomy = self.createTaxonomy(eachTaxonomyName, taxonomy)
                logging.debug("isCreateOk=%s, createdTaxonomy=%s", isCreateOk, createdTaxonomy)
                if isCreateOk and createdTaxonomy:
                    curTaxonomy = createdTaxonomy
                    logging.info("New created %s: name=%s,id=%s,slug=%s", taxonomy, curTaxonomy["name"], curTaxonomy["id"], curTaxonomy["slug"])
                else:
                    logging.error("Fail to create %s %s", taxonomy, eachTaxonomyName)

            if curTaxonomy:
                curTaxonomyId = curTaxonomy["id"]
                logging.debug("curTaxonomyId=%s", curTaxonomyId)
                taxonomyIdList.append(curTaxonomyId)
            else:
                logging.error("Fail search or create for %s: %s", taxonomy, eachTaxonomyName)

        logging.info("%s nameList=%s -> taxonomyIdList=%s", taxonomy, nameList, taxonomyIdList)
        return taxonomyIdList

    ################################################################################
    # Static Method
    ################################################################################

    @staticmethod
    def generateSlug(enTitle):
        """Generate Wordpress Post slug from english title

        Args:
            enTitle (str): english title of Evernote Note
        Returns:
            str
        Raises:
        Examples:
            input: 'Give the PIP replacement source to the Mac to speed up the download'
            output: 'give_pip_replacement_source_mac_speed_up_download'
        """
        slug = enTitle
        if not slug:
            return slug

        slug = slug.lower()
        # 'Xiaomi Sport uses and sets the Mi Band 4' -> 'xiaomi sport uses and sets the mi band 4'

        # special: 
        # (1) xxx'yyy -> xxxyyy
        # don't, can't, it's,there're
        # ->
        # dont, cant, its, therere
        slug = re.sub("(\w+)'(\w+)", "\1\2", slug)

        # (2) remove speical word: the to a is and ...
        # 'Give the PIP replacement source to the Mac to speed up the download'
        # -> 
        # 'Give PIP replacement source the Mac speed up download'
        # 
        # 'xiaomi sport uses and sets the mi band 4'
        # ->
        # 'xiaomi sport uses sets mi band 4'
        removeWordList = ["to", "the", "a", "are", "is", "and", "of", "in", "at"]
        for eachWord in removeWordList:
            removeInsideP = f"\s+{eachWord}\s+" # '\\s+to\\s+'
            slug = re.sub(removeInsideP, " ", slug, flags=re.I)
            # special: 'the road of water suzhou qingyuan huayan water concerns public number binding door number'
            removeStartP = f"^{eachWord}\s+"
            slug = re.sub(removeStartP, "", slug, flags=re.I)
            # Error: slug: Account registration and login in the Android APP of Bank of China -> account_registration_login_in_android_app_bank_chin
            # removeEndP = f"{eachWord}$"
            removeEndP = f"\s+{eachWord}$"
            # 'Account registration and login in the Android APP of Bank of China' -> 'account registration login android app bank china'
            slug = re.sub(removeEndP, "", slug, flags=re.I)

        # remove other special char
        slug = re.sub("[^\w]", "_", slug)
        # 'xiaomi_sport_uses_sets_mi_band_4'
        # '__' -> '_'
        slug = re.sub("_+", "_", slug)

        logging.info("slug: %s -> %s", enTitle, slug)
        # 'Xiaomi Sport uses and sets the Mi Band 4' -> 'xiaomi_sport_uses_sets_mi_band_4'
        # 'The road of water Suzhou Qingyuan Huayan water concerns the public number and the binding door number' -> 'road_water_suzhou_qingyuan_huayan_water_concerns_public_number_binding_door_number'

        # for debug
        if not re.match("\w+", slug):
            logging.warning("Not valid slug: %s", slug)

        return slug

    @staticmethod
    def processCommonResponse(resp):
        """Process common wordpress POST response for 
            POST /wp-json/wp/v2/media
            POST /wp-json/wp/v2/posts
            POST /wp-json/wp/v2/categories
            GET  /wp-json/wp/v2/categories
            POST /wp-json/wp/v2/tags
            GET  /wp-json/wp/v2/tags

        Args:
            resp (Response): requests response
        Returns:
            (bool, dict)
                True, created/searched item info
                False, error detail
        Raises:
        """
        isOk, respInfo = False, {}

        if resp.ok:
            respJson = resp.json()
            logging.debug("respJson=%s", respJson)
            """
            POST /wp-json/wp/v2/media
                {
                    "id": 70401,
                    "date": "2020-03-13T22:34:29",
                    "date_gmt": "2020-03-13T14:34:29",
                    "guid": {
                        "rendered": "https://www.crifan.org/files/pic/uploads/2020/03/f6956c30ef0b475fa2b99c2f49622e35.png",
                        "raw": "https://www.crifan.org/files/pic/uploads/2020/03/f6956c30ef0b475fa2b99c2f49622e35.png"
                    },
                    "modified": "2020-03-13T22:34:29",
                    ...
                    "slug": "f6956c30ef0b475fa2b99c2f49622e35",
                    "status": "inherit",
                    "type": "attachment",
                    "link": "https://www.crifan.org/f6956c30ef0b475fa2b99c2f49622e35/",
                    "title": {
                        "raw": "f6956c30ef0b475fa2b99c2f49622e35",
                        "rendered": "f6956c30ef0b475fa2b99c2f49622e35"
                    },
            
            POST /wp-json/wp/v2/posts
                {
                    "id": 70410,
                    "date": "2020-02-27T21:11:49",
                    "date_gmt": "2020-02-27T13:11:49",
                    "guid": {
                        "rendered": "https://www.crifan.org/?p=70410",
                        "raw": "https://www.crifan.org/?p=70410"
                    },
                    "modified": "2020-02-27T21:11:49",
                    "modified_gmt": "2020-02-27T13:11:49",
                    "password": "",
                    "slug": "mac_pip_change_source_server_to_spped_up_download",
                    "status": "draft",
                    "type": "post",
                    "link": "https://www.crifan.org/?p=70410",
                    "title": {
                        'raw": "【已解决】Mac中给pip更换源以加速下载",
                        "rendered": "【已解决】Mac中给pip更换源以加速下载"
                    },
                    "content": {
                        ...

            POST /wp-json/wp/v2/categories
                {
                    "id": 13223,
                    "count": 0,
                    "description": "",
                    "link": "https://www.crifan.org/category/mac-2/",
                    "name": "Mac",
                    "slug": "mac-2",
                    "taxonomy": "category",
                    "parent": 0,
                    "meta": [],
                    "_links": {
                        "self": [{
                        "href": "https://www.crifan.org/wp-json/wp/v2/categories/13223"
                        }],
                        "collection": [{
                        "href": "https://www.crifan.org/wp-json/wp/v2/categories"
                        }],
                        "about": [{
                        "href": "https://www.crifan.org/wp-json/wp/v2/taxonomies/category"
                        }],
                        "wp:post_type": [{
                        "href": "https://www.crifan.org/wp-json/wp/v2/posts?categories=13223"
                        }],
                        "curies": [{
                        "name": "wp",
                        "href": "https://api.w.org/{rel}",
                        "templated": True
                        }]
                    }
                }

            GET /wp-json/wp/v2/categories?search=Mac
                [
                    {
                        "id": 1639,
                        "count": 7,
                        "description": "",
                        "link": "https://www.crifan.org/category/work_and_job/operating_system_and_platform/mac/cocoa-mac/",
                        "name": "Cocoa",
                        "slug": "cocoa-mac",
                        "taxonomy": "category",
                        "parent": 1374,
                        "meta": [],
                        "_links": {
                            "self": [{
                            "href": "https://www.crifan.org/wp-json/wp/v2/categories/1639"
                            }],
                            "collection": [{
                            "href": "https://www.crifan.org/wp-json/wp/v2/categories"
                            }],
                            "about": [{
                            "href": "https://www.crifan.org/wp-json/wp/v2/taxonomies/category"
                            }],
                            "up": [{
                            "embeddable": True,
                            "href": "https://www.crifan.org/wp-json/wp/v2/categories/1374"
                            }],
                            "wp:post_type": [{
                            "href": "https://www.crifan.org/wp-json/wp/v2/posts?categories=1639"
                            }],
                            "curies": [{
                            "name": "wp",
                            "href": "https://api.w.org/{rel}",
                            "templated": True
                            }]
                        }
                    }, {
                        ...
                    }
                ]
            
            
            GET /wp-json/wp/v2/tags?search=%E5%88%87%E6%8D%A2
                %E5%88%87%E6%8D%A2=切换

                [
                    ...
                    }, {
                        "id": 1367,
                        "count": 12,
                        "description": "",
                        "link": "https://www.crifan.org/tag/%e5%88%87%e6%8d%a2/",
                        "name": "切换",
                        "slug": "%e5%88%87%e6%8d%a2",
                        "taxonomy": "post_tag",
                        "meta": [],
                        "_links": {
                            "self": [{
                            "href": "https://www.crifan.org/wp-json/wp/v2/tags/1367"
                            }],
                            "collection": [{
                            "href": "https://www.crifan.org/wp-json/wp/v2/tags"
                            }],
                            "about": [{
                            "href": "https://www.crifan.org/wp-json/wp/v2/taxonomies/post_tag"
                            }],
                            "wp:post_type": [{
                            "href": "https://www.crifan.org/wp-json/wp/v2/posts?tags=1367"
                            }],
                            "curies": [{
                            "name": "wp",
                            "href": "https://api.w.org/{rel}",
                            "templated": True
                            }]
                        }
                    }, {
                        ...
                    }
                ]

            POST /wp-json/wp/v2/tags
                {
                    "id": 13224,
                    "count": 0,
                    "description": "",
                    "link": "https://www.crifan.org/tag/gpu/",
                    "name": "GPU",
                    "slug": "gpu",
                    "taxonomy": "post_tag",
                    "meta": [],
                    "_links": {
                        "self": [{
                        "href": "https://www.crifan.org/wp-json/wp/v2/tags/13224"
                        }],
                        "collection": [{
                        "href": "https://www.crifan.org/wp-json/wp/v2/tags"
                        }],
                        "about": [{
                        "href": "https://www.crifan.org/wp-json/wp/v2/taxonomies/post_tag"
                        }],
                        "wp:post_type": [{
                        "href": "https://www.crifan.org/wp-json/wp/v2/posts?tags=13224"
                        }],
                        "curies": [{
                        "name": "wp",
                        "href": "https://api.w.org/{rel}",
                        "templated": True
                        }]
                    }
                }
            """
            if isinstance(respJson, dict):
                isOk = True

                if "id" in respJson:
                    newId = respJson["id"]
                    newSlug = respJson["slug"]
                    newLink = respJson["link"]
                    logging.debug("newId=%s, newSlug=%s, newLink=%s", newId, newSlug, newLink) # newId=13224, newSlug=gpu, newLink=https://www.crifan.org/tag/gpu/
                    respInfo = {
                        "id": newId, # 70393
                        "slug": newSlug, # f6956c30ef0b475fa2b99c2f49622e35
                        "link": newLink, # https://www.crifan.org/f6956c30ef0b475fa2b99c2f49622e35/
                    }

                    if "type" in respJson:
                        curType = respJson["type"]
                        if (curType == "attachment") or (curType == "post"):
                            respInfo["url"] = respJson["guid"]["rendered"]
                            # "url": newUrl, # https://www.crifan.org/files/pic/uploads/2020/03/f6956c30ef0b475fa2b99c2f49622e35.png
                            respInfo["title"] = respJson["title"]["rendered"]
                            # "title": newTitle, # f6956c30ef0b475fa2b99c2f49622e35
                            logging.debug("url=%s, title=%s", respInfo["url"], respInfo["title"])

                    if "taxonomy" in respJson:
                        curTaxonomy = respJson["taxonomy"]
                        # common for category/post_tag
                        respInfo["name"] = respJson["name"]
                        respInfo["description"] = respJson["description"]
                        logging.debug("name=%s, description=%s", respInfo["name"], respInfo["description"])

                        if curTaxonomy == "category":
                            respInfo["parent"] = respJson["parent"]
                            logging.debug("parent=%s", respInfo["parent"])
                else:
                    respInfo = respJson

                logging.debug("respInfo=%s", respInfo)
            elif isinstance(respJson, list):
                isOk = True
                respInfo = respJson
        else:
            # error example:
            # resp=<Response [403]> for GET https://www.crifan.org/wp-json/wp/v2/categories with para={'search': '印象笔记'}
            # ->
            # {'errCode': 403, 'errMsg': '{"code":"jwt_auth_invalid_token","message":"Expired token","data":{"status":403}}'}
            isOk = False
            # respInfo = resp.status_code, resp.text
            respInfo = {
                "errCode": resp.status_code,
                "errMsg": resp.text,
            }

        logging.debug("isOk=%s, respInfo=%s", isOk, respInfo)
        # isOk=True, respInfo={'id': 13224, 'slug': 'gpu', 'link': 'https://www.crifan.org/tag/gpu/', 'name': 'GPU', 'description': ''}
        # isOk=True, respInfo={'id': 13226, 'slug': '%e6%98%be%e5%8d%a1%e6%a8%a1%e5%bc%8f', 'link': 'https://www.crifan.org/tag/%e6%98%be%e5%8d%a1%e6%a8%a1%e5%bc%8f/', 'name': '显卡模式', 'description': ''}
        # isOk=True, respInfo={'code': 'jwt_auth_valid_token', 'data': {'status': 200}}
        return isOk, respInfo

    @staticmethod
    def findSameNameTaxonomy(name, taxonomyLit):
        """Search same taxonomy (category/tag) name from taxonomy (category/tag) list

        Args:
            name (str): category/tag name to find
            taxonomyLit (list): category/tag list
        Returns:
            found taxonomy info (dict)
        Raises:
        """
        foundTaxonomy = None

        sameNameTaxonomy = None
        lowercaseSameNameTaxonomy = None
        lowerName = name.lower() # 'mac'

        for eachTaxonomy in taxonomyLit:
            curTaxonomyName = eachTaxonomy["name"] # 'Cocoa', 'Mac'
            curTaxonomyLowerName = curTaxonomyName.lower() # 'cocoa', 'mac'
            if curTaxonomyName == name:
                sameNameTaxonomy = eachTaxonomy
                break
            elif curTaxonomyLowerName == lowerName:
                lowercaseSameNameTaxonomy = eachTaxonomy

        if sameNameTaxonomy:
            foundTaxonomy = sameNameTaxonomy
        elif lowercaseSameNameTaxonomy:
            foundTaxonomy = lowercaseSameNameTaxonomy

        return foundTaxonomy
