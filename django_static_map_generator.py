import globalmaptiles
import Image
import aggdraw
import os
import urllib

def convertColor(color):
    color = (int(color[0]*255),int(color[1]*255),int(color[2]*255))
    return color



class AbstractTileManager:
    def __init__(self, base_directory):
        pass

    def get_tile(self, x, y):
        """must be implemented by subclass"""
        raise NotImplementedError


class BingTileManager(AbstractTileManager):
    def __init__(self, base_directory):
        self.mt_counter = 0
        self.base_directory = base_directory
        self.TILE_SIZE = 256
        self.mercator = globalmaptiles.GlobalMercator()

    ## Returns a template URL for the virtualEarth
    def layer_url_template(self, layer):
        layers_name = ["r", "a", "h"]
        return 'http://' + layers_name[layer] + \
               '%i.ortho.tiles.virtualearth.net/tiles/' + \
               layers_name[layer] + '%s.png?g=%i'

    ## Returns the URL to the virtualEarth tile
    def get_url(self, counter, coord, layer):
        version = 392
        return self.layer_url_template(layer) % (counter, coord, version)

    def get_tile(self, x, y, zoom):
        self.mt_counter += 1
        self.mt_counter = self.mt_counter % 4 #(count using 1-4 servers)

        gtx, gty = self.mercator.GoogleTile(x, y, zoom)
        fl_name = os.path.join(self.base_directory, "bing_%s_%s_%s_%s.png" % (zoom, gtx, gty, self.TILE_SIZE))

        if not os.path.isfile(fl_name):
            quad_key = self.mercator.QuadTree(x, y, zoom)

            url = self.get_url(self.mt_counter, quad_key, 0)
            #print url
            f = urllib.urlopen(url)

            out_file = file(fl_name, "w")
            out_file.write(f.read())
            out_file.flush()
            out_file.close()
        return Image.open(fl_name)

class GoogleTileManager(AbstractTileManager):
    def __init__(self, base_directory):
        self.base_directory = base_directory
        self.TILE_SIZE = 256
        self.mercator = globalmaptiles.GlobalMercator()

    def get_tile(self, x, y, zoom):
        gtx, gty = self.mercator.GoogleTile(x, y, zoom)
        fl_name = os.path.join(self.base_directory, "%s_%s_%s_%s.png" % (zoom, gtx, gty, self.TILE_SIZE))

        if not os.path.isfile(fl_name):
            url = "https://mts0.google.com/vt/lyrs=t@129,r@185056370&hl=en&src=app&x=%d&y=%d&z=%d&s=" % (gtx, gty, zoom)
            #url = "http://mt1.google.com/vt/lyrs=m@139&hl=en&src=api&x=%d&y=%d&z=%d&s=Galileo" % (gtx, gty, zoom)x
            f = urllib.urlopen(url)

            out_file = file(fl_name, "w")
            out_file.write(f.read())
            out_file.flush()
            out_file.close()
        return Image.open(fl_name)

class StaticMapGenerator:
    def __init__(self, max_width = 1200, max_height = 1200, padding=100, base_directory = ""):
        self.MAX_MAP_WIDTH = max_width
        self.MAX_MAP_HEIGHT = max_height
        self.PADDING = padding
        self.mercator = globalmaptiles.GlobalMercator()
        self.lines = []
        self.markers = []
        self.polygons = []
        self.bbox = None
        self.ur_p_x = None
        self.ur_p_y = None
        self.ll_p_x = None
        self.ll_p_y = None
        self.ll_lat = None
        self.ll_long = None
        self.zoom = None
        self.image_width = None
        self.image_height = None
        self.TILE_SIZE = 256
        self.zoom_to_tile_manager = {}
        self.zoom_levels = []

        self.image = None

    def set_tile_manager(self, tile_manager, li_zoom_levels):
        for zl in li_zoom_levels:
            self.zoom_to_tile_manager[zl] = tile_manager
        self.zoom_levels = self.zoom_to_tile_manager.keys()
        self.zoom_levels.sort()
        self.zoom_levels.reverse()

    def add_polygon(self, poly):
        self.polygons.append(poly)
        self.reset_bbox()
        self.reset_size_n_zoom()

    def add_line(self, line):
        self.lines.append(line)
        self.reset_bbox()
        self.reset_size_n_zoom()

    def add_marker(self, marker):
        self.markers.append(marker)
        self.reset_bbox()
        self.reset_size_n_zoom()

    def all_geoms(self):
        return self.lines + self.markers + self.polygons

    def reset_bbox(self):
        for geom in self.all_geoms():
            check_coords = geom.extent

            if not self.bbox:
                self.bbox = [[check_coords[0], check_coords[1]], [check_coords[2], check_coords[3]]]
                continue

            check_ll, check_ur = [[check_coords[0], check_coords[1]], [check_coords[2], check_coords[3]]]

            if check_ll[0] < self.bbox[0][0]:
                self.bbox[0][0] = check_ll[0]
            if check_ll[1] < self.bbox[0][1]:
                self.bbox[0][1] = check_ll[1]

            if check_ur[0] > self.bbox[1][0]:
                self.bbox[1][0] = check_ur[0]
            if check_ur[1] > self.bbox[1][1]:
                self.bbox[1][1] = check_ur[1]

    def reset_size_n_zoom(self):
        #convert the bounds in lat/long to bounds in meters
        ur_m_x, ur_m_y = self.mercator.LatLonToMeters(self.bbox[1][1], self.bbox[1][0])
        ll_m_x, ll_m_y = self.mercator.LatLonToMeters(self.bbox[0][1], self.bbox[0][0])

        #FIND A ZOOM LEVEL THAT CAN DISPLAY THE ENTIRE TRAIL AT THE DEFINED MAP SIZE
        for zoom in self.zoom_levels: #[17,16,15,14,13,12,11,10,9,8]:
            ur_p_x, ur_p_y = self.mercator.MetersToPixels(ur_m_x, ur_m_y, zoom)
            ll_p_x, ll_p_y = self.mercator.MetersToPixels(ll_m_x, ll_m_y, zoom)

            if ((ur_p_x - ll_p_x) < self.MAX_MAP_WIDTH) and ((ur_p_y - ll_p_y) < self.MAX_MAP_HEIGHT):
                break


        self.zoom = zoom
        self.ur_p_x = int(ur_p_x) + self.PADDING
        self.ur_p_y = int(ur_p_y) + self.PADDING
        self.ll_p_x = int(ll_p_x) - self.PADDING
        self.ll_p_y = int(ll_p_y) - self.PADDING

        ll_m_x, ll_m_y = self.mercator.PixelsToMeters(self.ll_p_x, self.ll_p_y, self.zoom)
        self.ll_lat, self.ll_long = self.mercator.MetersToLatLon(ll_m_x, ll_m_y)

        self.image_width = self.ur_p_x - self.ll_p_x
        self.image_height = self.ur_p_y - self.ll_p_y

    def x_y_for_lat_long(self, lat, long):
        m_x, m_y = self.mercator.LatLonToMeters(lat, long)
        p_x, p_y = self.mercator.MetersToPixels(m_x, m_y, self.zoom)
        rx = p_x - self.ll_p_x
        ry = self.ur_p_y - p_y
        return [rx, ry]

    def generate_static_map(self, output_file):
        image = Image.new("RGB", (self.image_width, self.image_height))

        start_tile_x, start_tile_y = self.mercator.PixelsToTile(self.ll_p_x, self.ll_p_y)

        start_tile_origin_x = start_tile_x * self.TILE_SIZE
        start_tile_origin_y = start_tile_y * self.TILE_SIZE

        #PASTE ALL BASEMAP TILES ON THE IMAGE
        curr_x = start_tile_origin_x
        while (curr_x <= (self.ur_p_x + self.TILE_SIZE)):

            curr_y = start_tile_origin_y
            while (curr_y <= (self.ur_p_y + self.TILE_SIZE)):
                tile = self.zoom_to_tile_manager[self.zoom].get_tile(curr_x / self.TILE_SIZE, curr_y / self.TILE_SIZE, self.zoom)

                pos_y = (self.ur_p_y - curr_y) - self.TILE_SIZE

                image.paste(tile, (curr_x - self.ll_p_x, pos_y))

                curr_y += self.TILE_SIZE

            curr_x += self.TILE_SIZE
        d = aggdraw.Draw(image)
        p = aggdraw.Pen("red", 4.0, 150)

        #DRAW THE LINES
        for m_line in self.lines:
            for line in m_line.coords:
                coords = []
                for coord in [self.x_y_for_lat_long(lat, long) for long, lat in line]:
                    coords += coord
                d.line(coords, p)

        #DRAW THE POLYGONS ITERATING THROUGH PRESET COLORS
        ##TODO: SET COLOR OPTIONS VIA FUNCTION
        colors = ((141, 211, 199), (255, 255, 179), (190, 186, 218), (251, 128, 114), (128, 177, 211), (253, 180, 98))
        cnt = 0
        for m_poly in self.polygons:
            for poly in m_poly.coords:
                for ashape in poly:
                    coords = []
                    for coord in  [self.x_y_for_lat_long(lat, long) for long, lat in ashape]:
                        coords += coord
                    print coords
                    if not coords:
                        continue
                    if len(coords) % 2 != 0:
                        continue  #needs even number

                    color = convertColor(colors[cnt])
                    brush = aggdraw.Brush(color, 100)
                    pen = aggdraw.Pen(color, 4.0, 100)
                    d.polygon(coords, pen, brush)
                    cnt += 1
                    if cnt >= len(colors):
                        cnt = 0

        #print "saving"
        d.flush().save(output_file, "PNG")

def test():
    import django.contrib.gis.geos.collections
    x = StaticMapGenerator(base_directory=os.path.dirname(__file__))
    x.set_tile_manager(GoogleTileManager(os.path.dirname(__file__)), [15, 14, 13, 12, 11, 10, 9, 8])
    x.set_tile_manager(BingTileManager(os.path.dirname(__file__)), [17, 16])

    linestring = django.contrib.gis.geos.collections.LineString(((-111.9, 33.38), (-112.0, 33.43)))
    mlinestring  = django.contrib.gis.geos.collections.MultiLineString([linestring,])

    x.add_line(mlinestring)
    out_image = os.path.join(os.path.dirname(__file__), "out.png")
    x.generate_static_map(out_image)

if __name__ == "__main__":
    test()



