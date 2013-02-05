#!python

__author__ = "Curtis L. Olson < curtolson {at} flightgear {dot} org >"
__url__ = "http://gallinazo.flightgear.org"
__version__ = "1.0"
__license__ = "GPL v2"


import fileinput
import math
import string
import spline
import Polygon
import Polygon.Shapes


class Cutpos:
    def __init__(self, percent=None, front=None, rear=None, \
                     xpos=None, atstation=None, slope=None):
        self.percent = percent             # placed at % point in chord
        self.front = front                 # dist from front of chord
        self.rear = rear                   # dist from rear of chord
        self.xpos = xpos                   # abs position

        # if atstation + slope are defined, then the cut position will
        # be just like any other cut position at the 'root' station,
        # but offset by dist+slope for any other station.  This allows
        # straight stringers or aileron cut at arbitray angles
        # relative to the rest of the wing.
        self.atstation = atstation
        self.slope = slope

    # move the cutpos by dist amount
    def move(self, xdist=0.0):
        if self.percent != None:
            self.percent += xdist
        elif self.front != None:
            self.front += xdist
        elif self.rear != None:
            self.rear += xdist
        elif self.xpos != None:
            self.xpos += xdist


class Cutout:
    def __init__(self, side="top", orientation="tangent", cutpos=None, \
                     xsize=0.0, ysize=0.0):
        # note: specify a value for only one of percent, front, rear, or xpos
        self.side = side                   # {top, bottom}
        self.orientation = orientation     # {tangent, vertical}
        self.xsize = xsize                 # horizontal size
        self.ysize = ysize                 # vertical size
        self.cutpos = cutpos               # Cutpos()


class Contour:

    def __init__(self):
        self.name = ""
        self.description = ""
        self.top = []
        self.bottom = []
        self.poly = None
        self.labels = []
        self.saved_bounds = []        # see self.save_bounds() for details

    def dist_2d(self, pt1, pt2):
        dx = pt2[0]-pt1[0]
        dy = pt2[1]-pt1[1]
        return math.sqrt(dx*dx + dy*dy)

    def simple_interp(self, points, v):
        index = spline.binsearch(points, v)
        n = len(points) - 1
        if index < n:
            xrange = points[index+1][0] - points[index][0]
            yrange = points[index+1][1] - points[index][1]
	    # print(" xrange = $xrange\n")
            if xrange > 0.0001:
                percent = (v - points[index][0]) / xrange
                # print(" percent = $percent\n")
                return points[index][1] + percent * yrange
            else:
                return points[index][1]
        else:
            return points[index][1]

    def fit(self, maxpts = 30, maxerror = 0.1):
        self.top = list( self.curve_fit(self.top, maxpts, maxerror) )
        self.bottom = list( self.curve_fit(self.bottom, maxpts, maxerror) )

    def curve_fit(self, curve, maxpts = 30, maxerror = 0.1):
        wip = []

        # start with the end points
        n = len(curve)
        wip.append( curve[0] )
        wip.append( curve[n-1] )

        # iterate until termination conditions are met
        done = False
        while not done:
            maxy = 0
            maxx = 0
            maxdiff = 0
            maxi = -1
            # iterate over the orginal interior points
            for i in range(1, n-1):
                pt = curve[i]
                iy = self.simple_interp(wip, pt[0])
                diff = math.fabs(pt[1] - iy)
                if diff > maxdiff and diff > maxerror:
                    maxdiff = diff
                    maxi = i
                    maxx = pt[0]
                    maxy = pt[1]

            if maxi > -1:
                # found a match for a furthest off point
	        #print "($#wipx) inserting -> $maxx , $maxy at pos ";

                # find insertion point
                pos = 0
                wipn = len(wip)
                #print str(pos) + " " + str(wipn)
                while pos < wipn and maxx > wip[pos][0]:
                    pos += 1
                    #print pos
	        #print "$pos\n";
                wip.insert( pos, (maxx, maxy) )
            else:
                done = True

            if len(wip) >= maxpts:
                done = True

        return wip

    def display(self):
        for pt in self.top:
            print str(pt[0]) + " " + str(pt[1])
        for pt in self.bottom:
            print str(pt[0]) + " " + str(pt[1])

    # rotate a point about (0, 0)
    def rotate_point( self, pt, angle ):
        rad = math.radians(angle)
        newx = pt[0] * math.cos(rad) - pt[1] * math.sin(rad)
        newy = pt[1] * math.cos(rad) + pt[0] * math.sin(rad)
        return (newx, newy)

    def rotate(self, angle):
        newtop = []
        newbottom = []
        newlabels = []
        for pt in self.top:
            newtop.append( self.rotate_point(pt, angle) )
        for pt in self.bottom:
            newbottom.append( self.rotate_point(pt, angle) )
        for label in self.labels:
            newpt = self.rotate_point( (label[0], label[1]), angle)
            newlabels.append( (newpt[0], newpt[1], label[2], label[3] + angle, label[4]) )
        if self.poly != None:
            self.poly.rotate(math.radians(angle), 0.0, 0.0)
        self.top = list(newtop)
        self.bottom = list(newbottom)
        self.labels = list(newlabels)

    def scale(self, hsize, vsize):
        newtop = []
        newbottom = []
        newlabels = []
        for pt in self.top:
            newx = pt[0] * hsize
            newy = pt[1] * vsize
            newtop.append( (newx, newy) )
        for pt in self.bottom:
            newx = pt[0] * hsize
            newy = pt[1] * vsize
            newbottom.append( (newx, newy) )
        for label in self.labels:
            newx = ( label[0] * hsize )
            newy = ( label[1] * vsize )
            newlabels.append( (newx, newy, label[2], label[3], label[4]) )
        self.top = list(newtop)
        self.bottom = list(newbottom)
        self.labels = list(newlabels)

    def move(self, x, y):
        newtop = []
        newbottom = []
        newlabels = []
        for pt in self.top:
            newx = pt[0] + x
            newy = pt[1] + y
            newtop.append( (newx, newy) )
        for pt in self.bottom:
            newx = pt[0] + x
            newy = pt[1] + y
            newbottom.append( (newx, newy) )
        for label in self.labels:
            newx = label[0] + x
            newy = label[1] + y
            newlabels.append( (newx, newy, label[2], label[3], label[4]) )
        self.top = list(newtop)
        self.bottom = list(newbottom)
        self.labels = list(newlabels)

    # the saved "bounds" are used cooperatively to mark the size of
    # the part before any leading/trailing edge cutouts so that these
    # cuts don't cause us to lose the original size of the part and
    # our cut positions can remain constant through out the build
    # process.
    def save_bounds(self):
        self.saved_bounds = self.get_bounds()

    # given one of the possible ways to specify position, return the
    # actual position (relative to the original pre-cut part dimensions)
    def get_xpos(self, cutpos=None, station=None):
        if len(self.saved_bounds) == 0:
            print "need to call contour.save_bounds() after part created,"
            print "but before any cutouts are made"
            self.save_bounds()
        chord = self.saved_bounds[1][0] - self.saved_bounds[0][0]
        if cutpos.percent != None:
            xpos = self.saved_bounds[0][0] + chord * cutpos.percent
        elif cutpos.front != None:
            xpos = self.saved_bounds[0][0] + cutpos.front
        elif cutpos.rear != None:
            xpos = self.saved_bounds[1][0] - cutpos.rear
        elif cutpos.xpos != None:
            xpos = cutpos.xpos
        else:
            print "get_xpos() called with no valid cut position!!!"
        if cutpos.atstation != None and station != None:
            if cutpos.slope == None:
                cutpos.slope = 0.0
            lat_dist = math.fabs(station) - cutpos.atstation
            long_dist = lat_dist * cutpos.slope
            xpos += long_dist
        return xpos

    # given a line (point + slope) return the "xpos" of the
    # intersection with the contour (does not handle the special case
    # of a vertical slope in either line)
    def intersect(self, side="top", pt=None, slope=None):
        if side == "top":
            curve = list(self.top)
        else:
            curve = list(self.bottom)
        m1 = slope
        b1 = pt[1] - m1 * pt[0]
        n = len(curve)
        i = 0
        found = False
        while i < n+1 and not found:
            pt1 = curve[i]
            pt2 = curve[i+1]
            dx = pt2[0] - pt1[0]
            dy = pt2[1] - pt1[1]
            if math.fabs(dx) > 0.0001:
                m2 = dy / dx
                b2 = pt1[1] - m2 * pt1[0]
                if math.fabs(m1 - m2) > 0.0001:
                    x = (b2 - b1) / (m1 - m2)
                    if x >= pt1[0] and x <= pt2[0]:
                        found = True
                else:
                    print "parallel lines"
            else:
                print "vertical segment"
            i += 1
        if found:
            return x
        else:
            return None

    # trim everything front or rear of a given position
    def trim(self, side="top", discard="rear", cutpos=None, station=None):
        if side == "top":
            curve = list(self.top)
        else:
            curve = list(self.bottom)
        newcurve = []
        xpos = self.get_xpos(cutpos, station)
        ypos = self.simple_interp(curve, xpos)
        n = len(curve)
        i = 0
        if discard == "rear":
            # copy up to the cut point
            while i < n and curve[i][0] <= xpos:
                newcurve.append( curve[i] )
                i += 1
            if i < n:
                newcurve.append( (xpos, ypos) )
        else:
            # skip to the next point after the cut
            while i < n and curve[i][0] < xpos:
                #print "i=" + str(i) + " n=" + str(n) + " curve[i][0]=" + str(curve[i][0]) + " xpos=" + str(xpos)
                i += 1
            if i > 0:
                newcurve.append( (xpos, ypos) )
                #print "add=" + str( (xpos, ypos) )
            while i < n:
                newcurve.append( curve[i] )
                #print "add=" + str(curve[i])
                i += 1
        if side == "top":
            self.top = list(newcurve)
        else:
            self.bottom = list(newcurve)
 
    # build the Polygon representation of the shape from the
    # top/bottom curves.  The Polygon representation is used for doing
    # all the cutouts once the basic shape is created.  The Polygon
    # form can also spit out try strips and do a few other tricks that
    # are handy later on.
    def make_poly(self):
        reverse_top = list(self.top)
        reverse_top.reverse()
        shape = reverse_top + self.bottom
        self.poly = Polygon.Polygon(shape)
        # todo: add holes (should be easy, but want to work on other
        # aspects first)
        
    # side={top,bottom} (attached to top or bottom of airfoil)
    # orientation={tangent,vertical} (aligned vertically or flush with surface)
    # xpos={percent,front,rear,xpos} (position is relative to percent of chord,
    #      distance from front, distance from rear, or distance from chord
    #      zero point)
    # xsize=value (horizontal size of cutout)
    # ysize=value (vertical size)
    def cutout(self, cutout, station=None):
        if len(self.saved_bounds) == 0:
            print "need to call contour.save_bounds() after part created,"
            print "but before any cutouts are made"
            self.save_bounds()
        top = False
        if cutout.side == "top":
            top = True

        tangent = False
        if cutout.orientation == "tangent":
            tangent = True;

        # make the Polygon representation of this part if needed
        if self.poly == None:
            self.make_poly()

        # compute position of cutout
        xpos = self.get_xpos(cutout.cutpos, station=station)

        if top:
            curve = list(self.top)
        else:
            curve = list(self.bottom)
        ypos = self.simple_interp(curve, xpos)

        # make, position, and orient the cutout
        angle = 0
        if tangent:
            slopes = spline.derivative1(curve)
            index = spline.binsearch(curve, xpos)
            slope = slopes[index]
            rad = math.atan2(slope,1)
            angle = math.degrees(rad)
        if not top:
            angle += 180
            if angle > 360:
                angle -= 360
        xhalf = cutout.xsize / 2
        yhalf = cutout.ysize / 2
        # extend shape by yhalf past boundary so we get a clean cutout
        # with no "flash"
        r0 = self.rotate_point( (-xhalf, yhalf), angle )
        r1 = self.rotate_point( (-xhalf, -cutout.ysize), angle )
        r2 = self.rotate_point( (xhalf, -cutout.ysize), angle )
        r3 = self.rotate_point( (xhalf, yhalf), angle )

        p0 = ( r0[0] + xpos, r0[1] + ypos )
        p1 = ( r1[0] + xpos, r1[1] + ypos )
        p2 = ( r2[0] + xpos, r2[1] + ypos )
        p3 = ( r3[0] + xpos, r3[1] + ypos )

        hole = Polygon.Polygon( (p0, p1, p2, p3) )
        self.poly = self.poly - hole


    # build tab
    def buildtab(self, cutout, station=None):
        if len(self.saved_bounds) == 0:
            print "need to call contour.save_bounds() after part created,"
            print "but before any cutouts are made"
            self.save_bounds()
        top = False
        if cutout.side == "top":
            top = True

        # no support of tangent build tabs

        # make the Polygon representation of this part if needed
        if self.poly == None:
            self.make_poly()

        if top:
            curve = list(self.top)
        else:
            curve = list(self.bottom)

        # compute base position of cutout
        xpos = self.get_xpos(cutout.cutpos, station=station)
        ypos = self.simple_interp(curve, xpos)

        xhalf = cutout.xsize / 2
        x1 = xpos - xhalf
        x2 = xpos + xhalf
        y1 = self.simple_interp(curve, x1)
        y2 = self.simple_interp(curve, x2)
        ybase = y1
        if top:
            if y2 < y1:
                ybase = y2
        else:
            if y2 > y1:
                ybase = y2

        # make the tab
        p0 = (x1, ybase)
        if top:
            p1 = (x1, ypos + cutout.ysize)
            p2 = (x2, ypos + cutout.ysize)
        else:
            p1 = (x1, ypos - cutout.ysize)
            p2 = (x2, ypos - cutout.ysize)
        p3 = (x2, ybase)

        tab = Polygon.Polygon( (p0, p1, p2, p3) )
        self.poly = self.poly + tab


    def cutout_stringer(self, stringer, station=None):
        self.cutout( stringer, station )

    def add_build_tab(self, side="top", cutpos=None, \
                          xsize=0.0, yextra=0.0):
        # compute actual "x" position
        xpos = self.get_xpos(cutpos)

        # get current bounds
        bounds = self.get_bounds()

        # find the y value of the attach point and compute the
        # vertical size of the tab needed
        if side == "top":
            ypos = self.simple_interp(self.top, xpos)
            ysize = bounds[1][1] - ypos + yextra
        else:
            ypos = self.simple_interp(self.bottom, xpos)
            ysize = ypos - bounds[0][1] + yextra

        cutout = Cutout( side=side, orientation="vertical", \
                             cutpos=cutpos, \
                             xsize=xsize, ysize=ysize )

        # call the cutout method with negative ysize to create a tab
        self.buildtab(cutout)

    def cut_hole(self, xpos, ypos, radius):
        if self.poly == None:
            self.make_poly()
        hole = Polygon.Shapes.Circle(radius=radius, center=(xpos, ypos), \
                                         points=32)
        self.poly = self.poly - hole

    def add_label(self, xpos, ypos, size, rotate, text):
        self.labels.append( (xpos, ypos, size, rotate, text) )        

    def project_point(self, top, slopes, index, orig, ysize):
        slope = slopes[index]
        rad = math.atan2(slope,1)
        angle = math.degrees(rad)
        #print "xpos " + str(xpos) + " angle = " + str(angle)
        if not top:
            angle += 180
            if angle > 360:
                angle -= 360
        r0 = self.rotate_point( (0, ysize), angle )
        pt = ( r0[0] + orig[0], r0[1] + orig[1] )
        if top and pt[1] < 0.0:
            pt = (pt[0], 0.0)
        elif not top and pt[1] > 0.0:
            pt = (pt[0], 0.0)
        return pt

    def cutout_sweep(self, side="top", xstart=0, xsize=0, ysize=0):
        top = False
        if side == "top":
            top = True

        curve = []
        if top:
            curve = list(self.top)
        else:
            curve = list(self.bottom)

        n = len(curve)
        newcurve = []

        # nose portion
        i = 0
        while i < n and curve[i][0] < xstart:
            newcurve.append( curve[i] )
            i += 1

        # anchor sweep
        ypos = self.simple_interp(curve, xstart)
        newcurve.append( (xstart, ypos) )

        # sweep cutout
        slopes = spline.derivative1(curve)
        dist = 0.0
        xpos = xstart
        index = spline.binsearch(curve, xpos)
        first = True
        next_dist = 0
        while index < n and dist + next_dist <= xsize:
            dist += next_dist
            ypos = self.simple_interp(curve, xpos)
            pt = self.project_point(top, slopes, index, (xpos, ypos), -ysize)
            newcurve.append( pt )
            if index < n - 1:
                nextpt = curve[index+1]
                next_dist = self.dist_2d( (xpos, ypos), nextpt )
                xpos = nextpt[0]
            index += 1

        if index < n - 1:
            # finish sweep (advance x in proportion to get close to the
            # right total sweep dist
            rem = xsize - dist
            #print "rem = " + str(rem)
            pct = rem / next_dist
            #print "pct of next step = " + str(pct)
            xpos = curve[index-1][0]
            dx = curve[index][0] - xpos
            xpos += dx * rem
            ypos = self.simple_interp(curve, xpos)
            pt = self.project_point(top, slopes, index-1, (xpos, ypos), -ysize)
            newcurve.append( pt )
            newcurve.append( (xpos, ypos) )

        # tail portion
        while index < n:
            newcurve.append( curve[index] )
            index += 1

        if top:
            self.top = list(newcurve)
        else:
            self.bottom = list(newcurve)

    def get_bounds(self):
        if len(self.top) < 1:
            return ( (0,0), (0,0) )
        pt = self.top[0]
        minx = pt[0]
        maxx = pt[0]
        miny = pt[1]
        maxy = pt[1]
        for pt in self.top + self.bottom:
            if pt[0] < minx:
                minx = pt[0]
            if pt[0] > maxx:
                maxx = pt[0]
            if pt[1] < miny:
                miny = pt[1]
            if pt[1] > maxy:
                maxy = pt[1]
        return ( (minx, miny), (maxx, maxy) )
