import time

import cv2
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt

from labeling import label_vehicles
from statistics import calculate_speed
from vehicle import Vehicle

# If you don't want to save the output video every time you run the script, set it to False
# Else set it to True
SAVE_VIDEO = False

now = datetime.now()
DATE_STRING = now.strftime("%Y-%m-%d-%H-%M-%S")

INPUT_FILE_NAME = 'sample3.mp4'
INPUT_FILE_PATH = 'input/' + INPUT_FILE_NAME
OUTPUT_FILE_NAME = DATE_STRING + '.mp4'
OUTPUT_FILE_PATH = 'output/' + OUTPUT_FILE_NAME
MODEL_FILE_PATH = 'C:/Egyetem/5.felev/Temalab/yolov3-608.weights'
CLASSES_FILE_PATH = 'configfiles/coco.names'

cap = cv2.VideoCapture(INPUT_FILE_PATH)
FRAME_HEIGHT = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
FRAME_WIDTH = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
if SAVE_VIDEO:
    OUT = cv2.VideoWriter(OUTPUT_FILE_PATH, fourcc, 30, (FRAME_WIDTH, FRAME_HEIGHT))

# car, motorbike, bus, truck
ACCEPTED_CLASS_IDS = [2, 3, 5, 7]

YOLO_RES = 608
CONF_THRESHOLD = 0.35
NMS_THRESHOLD = 0.4

CLASS_NAMES = []

with open(CLASSES_FILE_PATH, 'rt') as f:
    CLASS_NAMES = f.read().rstrip('\n').split('\n')

MODEL_CONFIGURATION = 'configfiles/yolov3.cfg'
MODEL_WEIGHTS = MODEL_FILE_PATH

net = cv2.dnn.readNetFromDarknet(MODEL_CONFIGURATION, MODEL_WEIGHTS)

net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)

net.setPreferableTarget(cv2.dnn.DNN_TARGET_OPENCL)

previous_frame_vehicles = []
highest_id = 0

MAX_DETECTION_HEIGHT = FRAME_HEIGHT//2

FRAME_COUNT = 0
start_time = time.time()


def find_objects(outputs, image):
    global previous_frame_vehicles
    global highest_id
    ht, wt, cT = image.shape
    bounding_boxes = []
    class_ids = []
    ids = []
    confs = []
    vehicles = []
    detections = []

    for output_detections in outputs:
        for detection in output_detections:
            confidence_scores = detection[5:]
            class_id = np.argmax(confidence_scores)
            confidence = confidence_scores[class_id]
            if class_id in ACCEPTED_CLASS_IDS:
                if confidence > CONF_THRESHOLD:
                    w, h = int(detection[2] * wt), int(detection[3] * ht)
                    x, y = int((detection[0] * wt) - w / 2), int((detection[1] * ht) - h / 2)
                    if 8.5*FRAME_HEIGHT/10 > y > MAX_DETECTION_HEIGHT:
                        if 0.07*FRAME_WIDTH < x+w/2 < 0.93*FRAME_WIDTH:
                            if h > ht / 25:
                                if h < ht/5:
                                    bounding_boxes.append([x, y, w, h])
                                    vehicles.append(Vehicle(class_id, x, y, w, h, image, highest_id))
                                    class_ids.append(class_id)
                                    confs.append(float(confidence))
                                    detections.append([[x, y, w, h], confidence, class_id])

    indexes = cv2.dnn.NMSBoxes(bounding_boxes, confs, CONF_THRESHOLD, NMS_THRESHOLD)

    if len(indexes) > 0:
        for i in indexes:
            if vehicles[i].pos_y > MAX_DETECTION_HEIGHT:
                if len(previous_frame_vehicles) > 0:
                    closest = vehicles[i].find_closest(previous_frame_vehicles)[0]
                    if vehicles[i].in_range(closest.pos_x, closest.pos_y, closest.width/2, closest.height/2):
                        vehicles[i].id = closest.id
                        vehicles[i].age = closest.age + 1
                        previous_frame_vehicles.remove(closest)
                    else:
                        vehicles[i].id = highest_id
                        highest_id = highest_id + 1

                    if vehicles[i].id is None:
                        vehicles[i].id = highest_id
                        highest_id = highest_id + 1

                    calculate_speed(vehicles[i], closest, cap)
                else:
                    vehicles[i].id = highest_id
                    highest_id = highest_id + 1
                    vehicles[i].velocity = 'N/A'
                ids.append(vehicles[i].id)

    label_vehicles(indexes, bounding_boxes, vehicles, image)

    real_vehicles = []
    for i in indexes:
        real_vehicles.append(vehicles[i])
        box = bounding_boxes[i]
        y_offset = 0.5
        if vehicles[i].dir == 0:
            color_str = "green"
        elif vehicles[i].dir == 1:
            color_str = "blue"
        else:
            color_str = "red"
        if vehicles[i].class_id in class_ids[2:]:
            y_offset = 0.75
        plt.scatter(box[0] + box[2] / 2, FRAME_HEIGHT - box[1] - box[3] * y_offset, c=color_str, marker="s")

    previous_frame_vehicles = real_vehicles.copy()
    vehicles.clear()
    return len(indexes)


while True:
    success, img = cap.read()
    blob = cv2.dnn.blobFromImage(img, 1 / 255, (YOLO_RES, YOLO_RES), [0, 0, 0], crop=False)
    net.setInput(blob)

    layer_names = net.getLayerNames()

    output_names = [layer_names[i - 1] for i in net.getUnconnectedOutLayers()]

    output = net.forward(output_names)

    number_of_cars = find_objects(output, img)

    cv2.putText(img, f'TOTAL NUMBER OF VEHICLES: {highest_id}', (FRAME_WIDTH - 350, FRAME_HEIGHT - 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    cv2.imshow(DATE_STRING, img)

    FRAME_COUNT = FRAME_COUNT + 1

    if SAVE_VIDEO:
        img = cv2.resize(img, (FRAME_WIDTH, FRAME_HEIGHT))
        OUT.write(img)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        if SAVE_VIDEO:
            OUT.release()
        cv2.destroyAllWindows()
        plt.xlim(0, FRAME_WIDTH)
        # plt.ylim(0, FRAME_HEIGHT)
        plt.show()
        print(f'Processed frames: {FRAME_COUNT} frames under {round(time.time() - start_time, 2)} seconds '
              f'({round(FRAME_COUNT/(time.time() - start_time), 2)}FPS)')
        break
