import argparse

from PIL import Image

from robot_cameraman.pose_detection.detection import EdgeTpuPoseDetectionEngine
from robot_cameraman.pose_detection.draw import PoseDraw


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '-m', '--model', required=True, help='File path of .tflite file.')
    parser.add_argument(
        '-i', '--input', required=True, help='Image to be classified.')
    parser.add_argument(
        '--output',
        help='File path of the output image.')
    args = parser.parse_args()

    pose_detection_engine = EdgeTpuPoseDetectionEngine(model=args.model)
    pose_draw = PoseDraw()

    img = Image.open(args.input)
    poses = pose_detection_engine.detect(img)
    pose_draw.draw(img, poses)

    if args.output:
        img.save(args.output)
        print('Done. Results saved at', args.output)
    else:
        img.show()


def render_pose_standalone():
    from robot_cameraman.pose_detection.pose import Pose, KeyPoint
    # @formatter:off
    pose = Pose(nose=KeyPoint(y=224.17985916137695, x=317.26037979125977, confidence=0.5694627), left_eye=KeyPoint(y=216.31389141082764, x=325.1263427734375, confidence=0.6350124), right_eye=KeyPoint(y=218.28038692474365, x=301.5284538269043, confidence=0.36462), left_ear=KeyPoint(y=230.0793170928955, x=340.85826873779297, confidence=0.6350124), right_ear=KeyPoint(y=232.04581260681152, x=291.0405158996582, confidence=0.5694627), left_shoulder=KeyPoint(y=277.2750663757324, x=356.5901565551758, confidence=0.700562), right_shoulder=KeyPoint(y=283.17455291748047, x=267.442626953125, confidence=0.49981618), left_elbow=KeyPoint(y=230.0793170928955, x=411.6518783569336, confidence=0.700562), right_elbow=KeyPoint(y=228.11283588409424, x=201.8929672241211, confidence=0.700562), left_wrist=KeyPoint(y=145.52025318145752, x=411.6518783569336, confidence=0.700562), right_wrist=KeyPoint(y=155.3527021408081, x=183.53904724121094, confidence=0.5694627), left_hip=KeyPoint(y=420.8288383483887, x=351.34620666503906, confidence=0.19664899), right_hip=KeyPoint(y=412.9628849029541, x=283.17455291748047, confidence=0.36462), left_knee=KeyPoint(y=479.8235321044922, x=356.5901565551758, confidence=0.12290561), right_knee=KeyPoint(y=471.9575786590576, x=288.4185218811035, confidence=0.07374337), left_ankle=KeyPoint(y=475.89054107666016, x=338.2362747192383, confidence=0.07374337), right_ankle=KeyPoint(y=489.65600967407227, x=283.17455291748047, confidence=0.07374337))
    pose = Pose(nose=KeyPoint(y=281.20805740356445, x=388.0540084838867, confidence=0.36462), left_eye=KeyPoint(y=259.57666397094727, x=424.7618103027344, confidence=0.5694627), right_eye=KeyPoint(y=257.61016845703125, x=353.96820068359375, confidence=0.5694627), left_ear=KeyPoint(y=275.3085994720459, x=471.9575881958008, confidence=0.43016967), right_ear=KeyPoint(y=277.2750663757324, x=293.66249084472656, confidence=0.36462), left_shoulder=KeyPoint(y=428.69482040405273, x=492.93346405029297, confidence=0.19664899), right_shoulder=KeyPoint(y=438.5272407531738, x=283.17455291748047, confidence=0.19664899), left_elbow=KeyPoint(y=477.8570365905762, x=414.2738723754883, confidence=0.12290561), right_elbow=KeyPoint(y=460.158634185791, x=275.30858993530273, confidence=0.12290561), left_wrist=KeyPoint(y=291.04050636291504, x=485.06752014160156, confidence=0.024581134), right_wrist=KeyPoint(y=369.7000980377197, x=348.7242126464844, confidence=0.09422764), left_hip=KeyPoint(y=475.89054107666016, x=450.98167419433594, confidence=0.12290561), right_hip=KeyPoint(y=481.7900276184082, x=73.41562271118164, confidence=0.07374337), left_knee=KeyPoint(y=460.158634185791, x=506.04339599609375, confidence=0.09422764), right_knee=KeyPoint(y=471.9575786590576, x=26.219863891601562, confidence=0.05735597), left_ankle=KeyPoint(y=458.192138671875, x=419.51786041259766, confidence=0.12290561), right_ankle=KeyPoint(y=460.158634185791, x=243.84475708007812, confidence=0.12290562))
    pose = Pose(nose=KeyPoint(y=176.9840955734253, x=235.9787940979004, confidence=0.5694627), left_eye=KeyPoint(y=173.051118850708, x=249.08872604370117, confidence=0.6350124), right_eye=KeyPoint(y=176.9840955734253, x=228.11283111572266, confidence=0.49981618), left_ear=KeyPoint(y=171.084623336792, x=259.57666397094727, confidence=0.5694627), right_ear=KeyPoint(y=178.95057678222656, x=230.73482513427734, confidence=0.43016967), left_shoulder=KeyPoint(y=200.58197021484375, x=259.57666397094727, confidence=0.29907036), right_shoulder=KeyPoint(y=198.61547470092773, x=217.62489318847656, confidence=0.36462), left_elbow=KeyPoint(y=234.01230812072754, x=267.442626953125, confidence=0.36462), right_elbow=KeyPoint(y=234.01230812072754, x=204.51496124267578, confidence=0.36462), left_wrist=KeyPoint(y=245.81125259399414, x=238.60076904296875, confidence=0.43016967), right_wrist=KeyPoint(y=245.81125259399414, x=209.75893020629883, confidence=0.49981618), left_hip=KeyPoint(y=263.5096549987793, x=259.57666397094727, confidence=0.5694627), right_hip=KeyPoint(y=261.5431594848633, x=228.11283111572266, confidence=0.5694627), left_knee=KeyPoint(y=308.7389087677002, x=246.4667510986328, confidence=0.5694627), right_knee=KeyPoint(y=304.80594635009766, x=225.49083709716797, confidence=0.43016967), left_ankle=KeyPoint(y=353.9681911468506, x=249.08872604370117, confidence=0.49981618), right_ankle=KeyPoint(y=357.9011535644531, x=212.3809051513672, confidence=0.49981618))
    # @formatter:on
    image = Image.new('RGB', (640, 480), color=(73, 109, 137))
    PoseDraw().draw(image, [pose])
    image.show()


if __name__ == '__main__':
    main()
    # render_pose_standalone()
