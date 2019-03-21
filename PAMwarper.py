import xml.etree.ElementTree as ET
import os

folder =  "/home/user/rasters"
srcProj = 'EPSG:27572'
dstProj = 'EPSG:2154'



shellFile = folder + os.sep + 'rectify.sh'
inputFiles = [folder + os.sep + f for f in os.listdir(folder) if f.endswith(".jpg")]

with open(shellFile, 'w') as sh:
    for inputFile in inputFiles:

        basename, ext = os.path.splitext(os.path.basename(inputFile))
        pam = inputFile + ".aux.xml"
        if not os.path.exists(pam):
            continue
        points = inputFile + '.points'

        tree = ET.parse(pam)
        root = tree.getroot()

        order = next(root.iter('PolynomialOrder')).text

        def parseGCPs(tag, r=2):
            gcps = []
            for elem in root.iter(tag):
                x = None
                for gcp in elem.iter('Double'):
                    if x is None:
                        x = round(float(gcp.text),r)
                    else:
                        y = round(float(gcp.text),r)
                        gcps.append( [x, y] )
                        x = None
            return gcps

        def reversY(gcps):
            return [[gcp[0], -gcp[1]] for gcp in gcps]

        srcPts = parseGCPs('SourceGCPs') #image origin is top left, y coords are negatives numbers
        dstPts = parseGCPs('TargetGCPs')

        assert len(srcPts) == len(dstPts)
        n = len(srcPts)


        #write qgis's georeferencer gcps table
        with open(points, 'w') as f:
            f.write("mapX,mapY,pixelX,pixelY,enable,dX,dY,residual" + '\n')
            for i in range(n):
                values = map(str, dstPts[i] + srcPts[i] + [1,0,0,0])
                f.write(','.join(values) + '\n')

        #TRANSLATE
        srcPts = reversY(srcPts) #y number must be positive when used with gdal_translate -gcp parameter
        gcpArgs = []
        for i in range(n):
            values = map(str, srcPts[i] + dstPts[i])
            gcpArgs.append('-gcp ' + ' '.join(values))

        vrt = folder + os.sep + basename + '.vrt'
        args = ['gdal_translate', inputFile, vrt] + gcpArgs
        translate = ' '.join(args)
        sh.write(translate + '\n')

        #WARP
        warpOptions = {
        'rAlg':'cubic',
        'order':order,
        'compress':'JPEG',
        'srcProj':srcProj,
        'dstProj':dstProj,
        'input':vrt,
        'output':folder + os.sep + basename + '_rectified.tif'
        }

        warp = ('gdalwarp -r {rAlg} -order {order} -co COMPRESS={compress} '
        '-s_srs {srcProj} -t_srs {dstProj} {input} {output}').format(**warpOptions)
        sh.write(warp + '\n')
