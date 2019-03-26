import xml.etree.ElementTree as ET
import os
import logging

GDAL_PATH = '' #C:\\OSGeo4W\\bin\\

def parseGCPs(tree, tag, r=2):
    gcps = []
    for elem in tree.iter(tag):
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


def writeShFile(inFolder, outFolder, srcProjDefault, dstProj, targetExt, shellFilePath):

    with open(shellFilePath, 'w') as sh:
        for rootFolder, subFolders, files in os.walk(inFolder):
            inputFiles = [rootFolder + os.sep + f for f in files if f[-4:] in targetExt]

            wFolder = rootFolder.replace(inFolder, outFolder)
            if not os.path.exists(wFolder):
                os.makedirs(wFolder)

            for inputFile in inputFiles:
                log.info('Processing {}'.format(inputFile))

                basename, ext = os.path.splitext(os.path.basename(inputFile))
                pam = inputFile + ".aux.xml"
                if not os.path.exists(pam):
                    log.warning('Cannot process {} : no PAM file'.format(inputFile))
                    continue

                #QGIS Georeferencer GCPs table
                points = inputFile + '.points'

                tree = ET.parse(pam)
                rootTree = ET.parse(pam).getroot()

                try:
                    crsWKT = next(rootTree.iter('WKT')).text
                except StopIteration:
                    try:
                        crsWKT = next(rootTree.iter('SRS')).text
                    except StopIteration:
                        crsWKT = None
                        log.warning('{} : unknow CRS, set to default'.format(pam))

                if crsWKT is not None:
                    #TODO http://prj2epsg.org
                    if 'NTF' in crsWKT:
                        srcProj = 'EPSG:27572'
                    elif 'RGF93' in crsWKT:
                        srcProj = 'EPSG:2154'
                else:
                    srcProj = srcProjDefault

                srcPts = parseGCPs(rootTree, 'SourceGCPs') #image origin is top left, y coords are negatives numbers
                dstPts = parseGCPs(rootTree, 'TargetGCPs')

                if not srcPts or not dstPts:
                    log.warning('Cannot process {} : no GCPs defined'.format(pam))
                    continue

                if not len(srcPts) == len(dstPts):
                    log.error('Cannot process {} : no matching number of GCPs between source and taget points'.format(pam))
                    continue

                n = len(srcPts)

                try:
                    order = next(rootTree.iter('PolynomialOrder')).text
                except StopIteration as e:
                    log.warning('Cannot process {} : no polynomial order defined'.format(pam))
                    continue

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

                vrt = wFolder + os.sep + basename + '.vrt'
                args = [GDAL_PATH + 'gdal_translate', inputFile, vrt] + gcpArgs
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
                'output':wFolder + os.sep + basename + '_rectified.tif'
                }

                warp = (GDAL_PATH + 'gdalwarp -r {rAlg} -order {order} -co COMPRESS={compress} '
                '-s_srs {srcProj} -t_srs {dstProj} {input} {output}').format(**warpOptions)
                sh.write(warp + '\n')


if __name__ == "__main__":

    inFolder = '/home/eicc/Bureau/photos_anciennes/'
    outFolder = '/home/eicc/Bureau/warp/'

    srcProjDefault = 'EPSG:2154'
    dstProj = 'EPSG:2154'

    targetExt = [".jpg", ".jp2"]

    shellFile = outFolder + os.sep + 'rectify.sh'

    logFile = outFolder + os.sep + 'rectify.log'
    logLevel = logging.getLevelName('WARNING')
    logging.basicConfig(filename=logFile, filemode='w', level=logLevel)
    log = logging.getLogger(__name__)

    writeShFile(inFolder, outFolder, srcProjDefault, dstProj, targetExt, shellFile)
