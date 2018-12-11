from pywikibot import family


class OsmFamily(family.SingleSiteFamily):
    """
    Override default OSM family because data site and image repository do not work in the default
    """
    name = 'osm'
    domain = 'wiki.openstreetmap.org'
    code = 'en'

    def protocol(self, code):
        """Return https as the protocol for this family."""
        return 'https'

    def dbName(self, code):
        return 'wiki'

    def interface(self, code):
        return 'DataSite'

    def shared_image_repository(self, code):
        return ('commons', 'commons')
