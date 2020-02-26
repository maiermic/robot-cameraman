import struct
from typing import NamedTuple

RawCmd = NamedTuple('RawCmd', [
    ('id', int),
    ('payload', bytes),
])

# BOARD_VER 1u FIRMWARE_VER 2u STATE_FLAGS1 1u BOARD_FEATURES 2u CONNECTION_FLAG 1u FRW_EXTRA_ID 4u RESERVED 7b
BoardInfoInCmd = NamedTuple('BoardInfoInCmd', [
    ('board_ver', int),
    ('firmware_ver', int),
    ('state_flags1', int),
    ('board_features', int),
    ('connection_flag', int),
    ('frw_extra_id', int),
    ('reserved', bytes),
])

# DEVICE_ID 9b MCU_ID 12b EEPROM_SIZE 4u SCRIPT_SLOT1_SIZE 2u SCRIPT_SLOT2_SIZE 2u SCRIPT_SLOT3_SIZE 2u SCRIPT_SLOT4_SIZE 2u SCRIPT_SLOT5_SIZE 2u PROFILE_SET_SLOTS 1u PROFILE_SET_CUR 1u RESERVED 32b
BoardInfo3InCmd = NamedTuple('BoardInfo3InCmd', [
    ('device_id', bytes),
    ('mcu_id', bytes),
    ('eeprom_size', int),
    ('script_slot1_size', int),
    ('script_slot2_size', int),
    ('script_slot3_size', int),
    ('script_slot4_size', int),
    ('script_slot5_size', int),
    ('profile_set_slots', int),
    ('profile_set_cur', int),
    ('reserved', bytes),
])

# PROFILE_ID 1u P_AXIS_1 1u I_AXIS_1 1u D_AXIS_1 1u POWER_AXIS_1 1u INVERT_AXIS_1 1u POLES_AXIS_1 1u P_AXIS_2 1u I_AXIS_2 1u D_AXIS_2 1u POWER_AXIS_2 1u INVERT_AXIS_2 1u POLES_AXIS_2 1u P_AXIS_3 1u I_AXIS_3 1u D_AXIS_3 1u POWER_AXIS_3 1u INVERT_AXIS_3 1u POLES_AXIS_3 1u ACC_LIMITER_ALL 1u EXT_FC_GAIN_1 1s EXT_FC_GAIN_2 1s RC_MIN_ANGLE_AXIS_1 2s RC_MAX_ANGLE_AXIS_1 2s RC_MODE_AXIS_1 1u RC_LPF_AXIS_1 1u RC_SPEED_AXIS_1 1u RC_FOLLOW_AXIS_1 1u RC_MIN_ANGLE_AXIS_2 2s RC_MAX_ANGLE_AXIS_2 2s RC_MODE_AXIS_2 1u RC_LPF_AXIS_2 1u RC_SPEED_AXIS_2 1u RC_FOLLOW_AXIS_2 1u RC_MIN_ANGLE_AXIS_3 2s RC_MAX_ANGLE_AXIS_3 2s RC_MODE_AXIS_3 1u RC_LPF_AXIS_3 1u RC_SPEED_AXIS_3 1u RC_FOLLOW_AXIS_3 1u GYRO_TRUST 1u USE_MODEL 1u PWM_FREQ 1u SERIAL_SPPED 1u RC_TRIM_1 1s RC_TRIM_2 1s RC_TRIM_3 1s RC_DEADBAND 1u RC_EXPO_RATE 1u RC_VIRT_MODE 1u RC_MAP_ROLL 1u RC_MAP_PITCH 1u RC_MAP_YAW 1u RC_MAP_CMD 1u RC_MAP_FC_ROLL 1u RC_MAP_FC_PITCH 1u RC_MIX_FC_ROLL 1u RC_MIX_FC_PITCH 1u FOLLOW_MODE 1u FOLLOW_DEADBAND 1u FOLLOW_EXPO_RATE 1u FOLLOW_OFFSET_1 1s FOLLOW_OFFSET_2 1s FOLLOW_OFFSET_3 1s AXIS_TOP 1s AXIS_RIGHT 1s FRAME_AXIS_TOP 1s FRAME_AXIS_RIGHT 1s FRAME_IMU_POS 1u GYRO_DEADBAND 1u GYRO_SENS 1u I2C_SPEED_FAST 1u SKIP_GYRO_CALIB 1u RC_CMD_LOW 1u RC_CMD_MID 1u RC_CMD_HIGH 1u MENU_CMD_1 1u MENU_CMD_2 1u MENU_CMD_3 1u MENU_CMD_4 1u MENU_CMD_5 1u MENU_CMD_LONG 1u MOTOR_OUTPUT_1 1u MOTOR_OUTPUT_2 1u MOTOR_OUTPUT_3 1u BAT_THRESHOLD_ALARM 2s BAT_THRESHOLD_MOTORS 2s BAT_COMP_REF 2s BEEPER_MODES 1u FOLLOW_ROLL_MIX_START 1u FOLLOW_ROLL_MIX_RANGE 1u BOOSTER_POWER_1 1u BOOSTER_POWER_2 1u BOOSTER_POWER_3 1u FOLLOW_SPEED_1 1u FOLLOW_SPEED_2 1u FOLLOW_SPEED_3 1u FRAME_ANGLE_FROM_MOTORS 1u RC_MEMORY_1 2s RC_MEMORY_2 2s RC_MEMORY_3 2s SERVO1_OUT 1u SERVO2_OUT 1u SERVO3_OUT 1u SERVO4_OUT 1u SERVO_RATE 1u ADAPTIVE_PID_ENABLED 1u ADAPTIVE_PID_THRESHOLD 1u ADAPTIVE_PID_RATE 1u ADAPTIVE_PID_RECOVERY_FACTOR 1u FOLLOW_LPF_1 1u FOLLOW_LPF_2 1u FOLLOW_LPF_3 1u GENERAL_FLAGS1 2u PROFILE_FLAGS1 2u SPEKTRUM_MODE 1u ORDER_OF_AXES 1u EULER_ORDER 1u CUR_IMU 1u CUR_PROFILE_ID 1u
ReadParams3InCmd = NamedTuple('ReadParams3InCmd', [
    ('profile_id', int),
    ('p_axis_1', int),
    ('i_axis_1', int),
    ('d_axis_1', int),
    ('power_axis_1', int),
    ('invert_axis_1', int),
    ('poles_axis_1', int),
    ('p_axis_2', int),
    ('i_axis_2', int),
    ('d_axis_2', int),
    ('power_axis_2', int),
    ('invert_axis_2', int),
    ('poles_axis_2', int),
    ('p_axis_3', int),
    ('i_axis_3', int),
    ('d_axis_3', int),
    ('power_axis_3', int),
    ('invert_axis_3', int),
    ('poles_axis_3', int),
    ('acc_limiter_all', int),
    ('ext_fc_gain_1', int),
    ('ext_fc_gain_2', int),
    ('rc_min_angle_axis_1', int),
    ('rc_max_angle_axis_1', int),
    ('rc_mode_axis_1', int),
    ('rc_lpf_axis_1', int),
    ('rc_speed_axis_1', int),
    ('rc_follow_axis_1', int),
    ('rc_min_angle_axis_2', int),
    ('rc_max_angle_axis_2', int),
    ('rc_mode_axis_2', int),
    ('rc_lpf_axis_2', int),
    ('rc_speed_axis_2', int),
    ('rc_follow_axis_2', int),
    ('rc_min_angle_axis_3', int),
    ('rc_max_angle_axis_3', int),
    ('rc_mode_axis_3', int),
    ('rc_lpf_axis_3', int),
    ('rc_speed_axis_3', int),
    ('rc_follow_axis_3', int),
    ('gyro_trust', int),
    ('use_model', int),
    ('pwm_freq', int),
    ('serial_spped', int),
    ('rc_trim_1', int),
    ('rc_trim_2', int),
    ('rc_trim_3', int),
    ('rc_deadband', int),
    ('rc_expo_rate', int),
    ('rc_virt_mode', int),
    ('rc_map_roll', int),
    ('rc_map_pitch', int),
    ('rc_map_yaw', int),
    ('rc_map_cmd', int),
    ('rc_map_fc_roll', int),
    ('rc_map_fc_pitch', int),
    ('rc_mix_fc_roll', int),
    ('rc_mix_fc_pitch', int),
    ('follow_mode', int),
    ('follow_deadband', int),
    ('follow_expo_rate', int),
    ('follow_offset_1', int),
    ('follow_offset_2', int),
    ('follow_offset_3', int),
    ('axis_top', int),
    ('axis_right', int),
    ('frame_axis_top', int),
    ('frame_axis_right', int),
    ('frame_imu_pos', int),
    ('gyro_deadband', int),
    ('gyro_sens', int),
    ('i2c_speed_fast', int),
    ('skip_gyro_calib', int),
    ('rc_cmd_low', int),
    ('rc_cmd_mid', int),
    ('rc_cmd_high', int),
    ('menu_cmd_1', int),
    ('menu_cmd_2', int),
    ('menu_cmd_3', int),
    ('menu_cmd_4', int),
    ('menu_cmd_5', int),
    ('menu_cmd_long', int),
    ('motor_output_1', int),
    ('motor_output_2', int),
    ('motor_output_3', int),
    ('bat_threshold_alarm', int),
    ('bat_threshold_motors', int),
    ('bat_comp_ref', int),
    ('beeper_modes', int),
    ('follow_roll_mix_start', int),
    ('follow_roll_mix_range', int),
    ('booster_power_1', int),
    ('booster_power_2', int),
    ('booster_power_3', int),
    ('follow_speed_1', int),
    ('follow_speed_2', int),
    ('follow_speed_3', int),
    ('frame_angle_from_motors', int),
    ('rc_memory_1', int),
    ('rc_memory_2', int),
    ('rc_memory_3', int),
    ('servo1_out', int),
    ('servo2_out', int),
    ('servo3_out', int),
    ('servo4_out', int),
    ('servo_rate', int),
    ('adaptive_pid_enabled', int),
    ('adaptive_pid_threshold', int),
    ('adaptive_pid_rate', int),
    ('adaptive_pid_recovery_factor', int),
    ('follow_lpf_1', int),
    ('follow_lpf_2', int),
    ('follow_lpf_3', int),
    ('general_flags1', int),
    ('profile_flags1', int),
    ('spektrum_mode', int),
    ('order_of_axes', int),
    ('euler_order', int),
    ('cur_imu', int),
    ('cur_profile_id', int),
])

# PROFILE_ID 1u NOTCH_FREQ_AXIS_1 1u NOTCH_WIDTH_AXIS_1 1u NOTCH_FREQ_AXIS_2 1u NOTCH_WIDTH_AXIS_2 1u NOTCH_FREQ_AXIS_3 1u NOTCH_WIDTH_AXIS_3 1u LPF_FREQ_1 2u LPF_FREQ_2 2u LPF_FREQ_3 2u FILTERS_EN_1 1u FILTERS_EN_2 1u FILTERS_EN_3 1u ENCODER_OFFSET_1 2s ENCODER_OFFSET_2 2s ENCODER_OFFSET_3 2s ENCODER_FLD_OFFSET_1 2s ENCODER_FLD_OFFSET_2 2s ENCODER_FLD_OFFSET_3 2s ENCODER_MANUAL_SET_TIME_1 1u ENCODER_MANUAL_SET_TIME_2 1u ENCODER_MANUAL_SET_TIME_3 1u MOTOR_HEATING_FACTOR_1 1u MOTOR_HEATING_FACTOR_2 1u MOTOR_HEATING_FACTOR_3 1u MOTOR_COOLING_FACTOR_1 1u MOTOR_COOLING_FACTOR_2 1u MOTOR_COOLING_FACTOR_3 1u RESERVED 2b FOLLOW_INSIDE_DEADBAND 1u MOTOR_MAG_LINK_1 1u MOTOR_MAG_LINK_2 1u MOTOR_MAG_LINK_3 1u MOTOR_GEARING_1 2u MOTOR_GEARING_2 2u MOTOR_GEARING_3 2u ENCODER_LIMIT_MIN_1 1s ENCODER_LIMIT_MIN_2 1s ENCODER_LIMIT_MIN_3 1s ENCODER_LIMIT_MAX_1 1s ENCODER_LIMIT_MAX_2 1s ENCODER_LIMIT_MAX_3 1s NOTCH1_GAIN_1 1s NOTCH1_GAIN_2 1s NOTCH1_GAIN_3 1s NOTCH2_GAIN_1 1s NOTCH2_GAIN_2 1s NOTCH2_GAIN_3 1s NOTCH3_GAIN_1 1s NOTCH3_GAIN_2 1s NOTCH3_GAIN_3 1s BEEPER_VOLUME 1u ENCODER_GEAR_RATIO_1 2u ENCODER_GEAR_RATIO_2 2u ENCODER_GEAR_RATIO_3 2u ENCODER_TYPE_1 1u ENCODER_TYPE_2 1u ENCODER_TYPE_3 1u ENCODER_CFG_1 1u ENCODER_CFG_2 1u ENCODER_CFG_3 1u OUTER_P_1 1u OUTER_P_2 1u OUTER_P_3 1u OUTER_I_1 1u OUTER_I_2 1u OUTER_I_3 1u MAG_AXIS_TOP 1s MAG_AXIS_RIGHT 1s MAG_TRUST 1u MAG_DECLINATION 1s ACC_LPF_FREQ 2u D_TERM_LPF_FREQ_1 1u D_TERM_LPF_FREQ_2 1u D_TERM_LPF_FREQ_3 1u
ReadParamsExtInCmd = NamedTuple('ReadParamsExtInCmd', [
    ('profile_id', int),
    ('notch_freq_axis_1', int),
    ('notch_width_axis_1', int),
    ('notch_freq_axis_2', int),
    ('notch_width_axis_2', int),
    ('notch_freq_axis_3', int),
    ('notch_width_axis_3', int),
    ('lpf_freq_1', int),
    ('lpf_freq_2', int),
    ('lpf_freq_3', int),
    ('filters_en_1', int),
    ('filters_en_2', int),
    ('filters_en_3', int),
    ('encoder_offset_1', int),
    ('encoder_offset_2', int),
    ('encoder_offset_3', int),
    ('encoder_fld_offset_1', int),
    ('encoder_fld_offset_2', int),
    ('encoder_fld_offset_3', int),
    ('encoder_manual_set_time_1', int),
    ('encoder_manual_set_time_2', int),
    ('encoder_manual_set_time_3', int),
    ('motor_heating_factor_1', int),
    ('motor_heating_factor_2', int),
    ('motor_heating_factor_3', int),
    ('motor_cooling_factor_1', int),
    ('motor_cooling_factor_2', int),
    ('motor_cooling_factor_3', int),
    ('reserved', bytes),
    ('follow_inside_deadband', int),
    ('motor_mag_link_1', int),
    ('motor_mag_link_2', int),
    ('motor_mag_link_3', int),
    ('motor_gearing_1', int),
    ('motor_gearing_2', int),
    ('motor_gearing_3', int),
    ('encoder_limit_min_1', int),
    ('encoder_limit_min_2', int),
    ('encoder_limit_min_3', int),
    ('encoder_limit_max_1', int),
    ('encoder_limit_max_2', int),
    ('encoder_limit_max_3', int),
    ('notch1_gain_1', int),
    ('notch1_gain_2', int),
    ('notch1_gain_3', int),
    ('notch2_gain_1', int),
    ('notch2_gain_2', int),
    ('notch2_gain_3', int),
    ('notch3_gain_1', int),
    ('notch3_gain_2', int),
    ('notch3_gain_3', int),
    ('beeper_volume', int),
    ('encoder_gear_ratio_1', int),
    ('encoder_gear_ratio_2', int),
    ('encoder_gear_ratio_3', int),
    ('encoder_type_1', int),
    ('encoder_type_2', int),
    ('encoder_type_3', int),
    ('encoder_cfg_1', int),
    ('encoder_cfg_2', int),
    ('encoder_cfg_3', int),
    ('outer_p_1', int),
    ('outer_p_2', int),
    ('outer_p_3', int),
    ('outer_i_1', int),
    ('outer_i_2', int),
    ('outer_i_3', int),
    ('mag_axis_top', int),
    ('mag_axis_right', int),
    ('mag_trust', int),
    ('mag_declination', int),
    ('acc_lpf_freq', int),
    ('d_term_lpf_freq_1', int),
    ('d_term_lpf_freq_2', int),
    ('d_term_lpf_freq_3', int),
])

ReadParamsExt2InCmd = NamedTuple('ReadParamsExt2InCmd', [

])

ReadParamsExt3InCmd = NamedTuple('ReadParamsExt3InCmd', [

])

RealtimeData3InCmd = NamedTuple('RealtimeData3InCmd', [
    ('acc_data_axis_1', int),
    ('gyro_data_axis_1', int),
    ('acc_data_axis_2', int),
    ('gyro_data_axis_2', int),
    ('acc_data_axis_3', int),
    ('gyro_data_axis_3', int),
    ('serial_err_cnt', int),
    ('system_error', int),
    ('system_sub_error', int),
    ('reserved', bytes),
    ('rc_roll', int),
    ('rc_pitch', int),
    ('rc_yaw', int),
    ('rc_cmd', int),
    ('ext_fc_roll', int),
    ('ext_fc_pitch', int),
    ('imu_angle_1', int),
    ('imu_angle_2', int),
    ('imu_angle_3', int),
    ('frame_imu_angle_1', int),
    ('frame_imu_angle_2', int),
    ('frame_imu_angle_3', int),
    ('target_angle_1', int),
    ('target_angle_2', int),
    ('target_angle_3', int),
    ('cycle_time', int),
    ('i2c_error_count', int),
    ('error_code', int),
    ('bat_level', int),
    ('rt_data_flags', int),
    ('cur_imu', int),
    ('cur_profile', int),
    ('motor_power_1', int),
    ('motor_power_2', int),
    ('motor_power_3', int),
])

RealtimeData4InCmd = NamedTuple('RealtimeData4InCmd', [
    ('acc_data_axis_1', int),
    ('gyro_data_axis_1', int),
    ('acc_data_axis_2', int),
    ('gyro_data_axis_2', int),
    ('acc_data_axis_3', int),
    ('gyro_data_axis_3', int),
    ('serial_err_cnt', int),
    ('system_error', int),
    ('system_sub_error', int),
    ('reserved_3', bytes),
    ('rc_roll', int),
    ('rc_pitch', int),
    ('rc_yaw', int),
    ('rc_cmd', int),
    ('ext_fc_roll', int),
    ('ext_fc_pitch', int),
    ('imu_angle_1', int),
    ('imu_angle_2', int),
    ('imu_angle_3', int),
    ('frame_imu_angle_1', int),
    ('frame_imu_angle_2', int),
    ('frame_imu_angle_3', int),
    ('target_angle_1', int),
    ('target_angle_2', int),
    ('target_angle_3', int),
    ('cycle_time', int),
    ('i2c_error_count', int),
    ('error_code', int),
    ('bat_level', int),
    ('rt_data_flags', int),
    ('cur_imu', int),
    ('cur_profile', int),
    ('motor_power_1', int),
    ('motor_power_2', int),
    ('motor_power_3', int),
    ('stator_rotor_angle_1', int),
    ('stator_rotor_angle_2', int),
    ('stator_rotor_angle_3', int),
    ('reserved_4_0', bytes),
    ('balance_error_1', int),
    ('balance_error_2', int),
    ('balance_error_3', int),
    ('current', int),
    ('mag_data_1', int),
    ('mag_data_2', int),
    ('mag_data_3', int),
    ('imu_temperature', int),
    ('frame_imu_temperature', int),
    ('imu_g_err', int),
    ('imu_h_err', int),
    ('motor_out_1', int),
    ('motor_out_2', int),
    ('motor_out_3', int),
    ('reserved_4_1', bytes),
])

ConfirmInCmd = NamedTuple('ConfirmInCmd', [

])

ErrorInCmd = NamedTuple('ErrorInCmd', [

])

GetAnglesInCmd = NamedTuple('GetAnglesInCmd', [
    ('imu_angle_1', int),
    ('target_angle_1', int),
    ('target_speed_1', int),
    ('imu_angle_2', int),
    ('target_angle_2', int),
    ('target_speed_2', int),
    ('imu_angle_3', int),
    ('target_angle_3', int),
    ('target_speed_3', int),
])

GetAnglesExtInCmd = NamedTuple('GetAnglesExtInCmd', [

])

ReadProfileNamesInCmd = NamedTuple('ReadProfileNamesInCmd', [

])

I2cReadRegBufInCmd = NamedTuple('I2cReadRegBufInCmd', [

])

AutoPidInCmd = NamedTuple('AutoPidInCmd', [

])

DebugVarsInfo3InCmd = NamedTuple('DebugVarsInfo3InCmd', [

])

DebugVars3InCmd = NamedTuple('DebugVars3InCmd', [

])

ReadExternalDataInCmd = NamedTuple('ReadExternalDataInCmd', [

])

SetAdjVarsValInCmd = NamedTuple('SetAdjVarsValInCmd', [

])

ReadAdjVarsCfgInCmd = NamedTuple('ReadAdjVarsCfgInCmd', [

])

ResetInCmd = NamedTuple('ResetInCmd', [

])

EepromReadInCmd = NamedTuple('EepromReadInCmd', [

])

CalibInfoInCmd = NamedTuple('CalibInfoInCmd', [

])

ReadFileInCmd = NamedTuple('ReadFileInCmd', [

])

ScriptDebugInCmd = NamedTuple('ScriptDebugInCmd', [

])

AhrsHelperInCmd = NamedTuple('AhrsHelperInCmd', [

])

RealtimeDataCustomInCmd = NamedTuple('RealtimeDataCustomInCmd', [

])

AdjVarsStateInCmd = NamedTuple('AdjVarsStateInCmd', [

])

ReadRcInputsInCmd = NamedTuple('ReadRcInputsInCmd', [

])

EventInCmd = NamedTuple('EventInCmd', [

])

ExtImuDebugInfoInCmd = NamedTuple('ExtImuDebugInfoInCmd', [

])


# outgoing CMD_CONTROL - control gimbal movement
class ControlOutCmd(NamedTuple):
    roll_mode: int
    pitch_mode: int
    yaw_mode: int
    roll_speed: int
    roll_angle: int
    pitch_speed: int
    pitch_angle: int
    yaw_speed: int
    yaw_angle: int

    def pack(self) -> bytes:
        return struct.pack('<BBBhhhhhh', *self)
