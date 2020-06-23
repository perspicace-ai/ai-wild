
# CCF_filenames_to_json_v2.py
#
# Take a directory of images in which species labels are encoded by folder
# names, and produces a COCO-style .json file and csv file
#

"""
Assumes last-level subdirectory encodes groundtruth category (if sorted)
If path contains fewer than 2 directory levels, e.g., {location}\{category}\{image.jpg},
program will assign "unlabeled" category.  If you are working with sorted images, please ensure
there is at least one parent directory present below the image_dir, generally a {location} or {capture_date} indication
"""

#%% Constants and imports

import json
import io
import os
from pathlib import PurePath
import sys
import argparse
import uuid
import csv
import warnings
import datetime
from PIL import Image

# from the ai4eutils repo; placed copy of path_utils.py in cameratraps/data_management/importers
# because PYTHONPATH does not appear to be used, although correctly set...
from path_utils import find_images


def main():

    parser = argparse.ArgumentParser(description='Takes inventory of images on disk including groundtruth if present and generates csv and COCO json style listings.')

    image_dir = r'C:\xxx\github\cameratraps\images'
    #image_dir = ''
    output_prefix = r'CCF_experiment'
    #output_prefix = ''

    parser.add_argument('--output_prefix', action='store', type=str, default='', help='Output prefix to be used with csv and json output. ' + \
                        ' Output files will be stored in the root of the image_dir using current timestamp.')
    parser.add_argument('--image_dir', action='store', type=str, default='', help='Absolute path to images, with option for recursion')
    parser.add_argument('--recursive', action='store_true', help='Conduct recursive search for images')
    parser.add_argument('--store_image_dims', action='store_true', help='Store image dimensions')

    if len(sys.argv[1:])==0:
        parser.print_help()
        parser.exit()

    args = parser.parse_args()

    assert os.path.exists(args.image_dir), 'Specified image path does not exist'

    if len(args.output_prefix) > 0:
        output_prefix = args.output_prefix
    if len(args.image_dir) > 0:
        image_dir = args.image_dir


    timestamp = datetime.datetime.utcnow().strftime('%Y.%m.%d.%H%M')
    outputJsonFilename = os.path.join(image_dir,output_prefix + '.' + timestamp + '.json')
    outputCsvFilename = os.path.join(image_dir,output_prefix + '.' + timestamp + '.csv')

    outputEncoding = 'utf-8'
    maxFiles = -1

    info = {}
    info['year'] = 2020
    info['version'] = '2.0'
    info['description'] = 'Cheetah Conservation Fund Camera Traps in COCO json format'
    info['contributor'] = 'Kristina Kermanshahche, PERSPICACE INC'
    info['date_created'] = str(datetime.date.today())


    # Each element will be a list of relative path/full path/width/height/groundtruth
    classList = {}
    fileInfo = []
    nonImages = []
    nFiles = 0

    print('Enumerating files from {} to {}'.format(image_dir,outputCsvFilename))

    image_files = find_images(image_dir,args.recursive)
    print('Enumerated {} images'.format(len(image_files)))

    with io.open(outputCsvFilename, "w", encoding=outputEncoding) as outputFileHandle:

        for fname in image_files:

            nFiles = nFiles + 1
            if maxFiles >= 0 and nFiles > maxFiles:
                print('Warning: early break at {} files'.format(maxFiles))
                break

            fullPath = fname
            relativePath = os.path.relpath(fullPath,image_dir)

            if maxFiles >= 0:
                print(relativePath)

            h = -1
            w = -1

            if args.store_image_dims:

                # Read the image
                try:

                    im = Image.open(fullPath)
                    h = im.height
                    w = im.width

                except:
                    # Corrupt or not an image
                    nonImages.append(fullPath)
                    continue

            ## extract groundtruth category from last-level subdirectory, see note above
            p = PurePath(relativePath)  # p.parts = [{root},{location},{+-varying...},{+-category},{filename}]
            if len(p.parts) > 2:
                className = p.parts[(len(p.parts)-2)]
                className = className.lower().strip()
            else:
                className = 'unlabeled'

            ## extract location, capture_date, capture_time, capture_sequence from filename
            iname = p.parts[(len(p.parts)-1)]

            if len(iname.split('_')) > 4:
            #CCF images captured prior to 2019, the naming convention was {location}__{YYYY}-{MM}-{DD}__{HH}-{MM}-{SS}_{seqnum}.JPG
            #       e.g., Field5PlayTree__2016-06-15__07-06-35_2722.JPG
                location = iname.split('_')[0]
                capture_date = str(iname.split('_')[2]) + ' ' + str(iname.split('_')[4]).replace('-', ':')
                seq_id = str(iname.split('_')[5]).replace('.JPG','')

            elif len(iname.split('_')) == 4:
            #CCF images captured since 2019, the naming convention is {YYYYMMDD}_{HHMMSS}_{location}_{seqnum}.JPG
            #       e.g., 20200408_190800_FieldEdgeTrough_000118.JPG
                capture_date = str(iname.split('_')[0]) + ' ' + str(iname.split('_')[1])
                location = iname.split('_')[2]
                seq_id = str(iname.split('_')[3]).replace('.JPG','')

            else:
                location = 'Supplemental'
                capture_date = ''
                seq_id = ''

            if className in classList:
                classList[className] += 1
            else:
                classList[className] = 1

            # Store file info
            imageInfo = [relativePath, fullPath, location, capture_date, seq_id, w, h, className]
            fileInfo.append(imageInfo)

            # Write to output file
            outputFileHandle.write('"' + relativePath + '"' + ',' +
                                   '"' + fullPath + '"' + ',' +
                                   '"' + location + '"' + ',' +
                                   '"' + capture_date + '"' + ',' +
                                   '"' + seq_id + '"' + ',' +
                                   str(w) + ',' + str(h) + ','
                                   '"' + className + '"' + '\n')
        # ...for each image file

    print("Finished writing {} file names to {}".format(nFiles,outputCsvFilename))

    classNames = list(classList.keys())

    # We like 'empty' to be class 0
    if 'empty' in classNames:
        classNames.remove('empty')
    classNames.insert(0,'empty')

    print('Finished enumerating {} classes'.format(len(classList)))

    #%% Assemble dictionaries

    images = []
    annotations = []
    categories = []

    categoryNameToId = {}
    idToCategory = {}
    imageIdToImage = {}
    nextId = 0

    for categoryName in classNames:

        catId = nextId
        nextId += 1
        categoryNameToId[categoryName] = catId
        newCat = {}
        newCat['id'] = categoryNameToId[categoryName]
        newCat['name'] = categoryName
        newCat['count'] = 0
        categories.append(newCat)
        idToCategory[catId] = newCat

    # ...for each category
    # Each element is a list of relative path/full path/width/height/className

    for iRow,row in enumerate(fileInfo):
        relativePath = row[0]
        loc = row[2]
        dt = row[3]
        seq = row[4]
        w = row[5]
        h = row[6]
        className = row[7]

        assert className in categoryNameToId
        categoryId = categoryNameToId[className]

        im = {}
        im['id'] = str(uuid.uuid1())
        im['file_name'] = relativePath
        im['location'] = loc
        im['datetime'] = dt
        im['seq_id'] = seq
        im['height'] = h
        im['width'] = w
        images.append(im)
        imageIdToImage[im['id']] = im

        ann = {}
        ann['id'] = str(uuid.uuid1())
        ann['image_id'] = im['id']
        ann['category_id'] = categoryId
        annotations.append(ann)

        cat = idToCategory[categoryId]
        cat['count'] += 1

    # ...for each image

    print('Finished assembling dictionaries')

    #%% Write output .json

    data = {}
    data['info'] = info
    data['images'] = images
    data['annotations'] = annotations
    data['categories'] = categories

    json.dump(data, open(outputJsonFilename,'w'), indent=4)

    print('Finished writing json to {}'.format(outputJsonFilename))



if __name__ == '__main__':

    main()
