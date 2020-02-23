import struct
from typing import Optional

from simplebgc.command_ids import *
from simplebgc.commands import *


# 1u => int
# 1s => int
# 2u => int
# 2s => int
# 4u => int
# 4f => float
# 4s => int
# string – ASCII character array, first byte is array size
# Nb => bytes


# 1u => B
# 1s => b
# 2u => H
# 2s => h
# 4u => I
# 4f => f
# 4s => i
# string – ASCII character array, first byte is array size
# Nb => Ns


# function convertFormat(format) {
#   return format.split(' ').map(type => {
#     if (type[type.length - 1] === 'b') return type.replace('b', 's');
# 	const converted = {
#       '1u': 'B',
#       '1s': 'b',
#       '2u': 'H',
#       '2s': 'h',
#       '4u': 'I',
#       '4f': 'f',
#       '4s': 'i',
#     }[type];
#     return converted;
#   }).join('');
# }


def parse_board_info_cmd(payload: bytes) -> BoardInfoInCmd:
    # noinspection PyProtectedMember
    return BoardInfoInCmd._make(struct.unpack('<BHBHBI7s', payload))


def parse_board_info_3_cmd(payload: bytes) -> BoardInfo3InCmd:
    # noinspection PyProtectedMember
    return BoardInfo3InCmd._make(struct.unpack('<9s12sIHHHHHBB32s', payload))


def parse_read_params_3_cmd(payload: bytes) -> ReadParams3InCmd:
    # noinspection PyProtectedMember
    return ReadParams3InCmd._make(struct.unpack('<BBBBBBBBBBBBBBBBBBBBbbhhBBBBhhBBBBhhBBBBBBBBbbbBBBBBBBBBBBBBBbbbbbbbBBBBBBBBBBBBBBBBBhhhBBBBBBBBBBhhhBBBBBBBBBBBBHHBBBBB', payload))


def parse_read_params_ext_cmd(payload: bytes) -> ReadParamsExtInCmd:
    # noinspection PyProtectedMember
    return ReadParamsExtInCmd._make(struct.unpack('<BBBBBBBHHHBBBhhhhhhBBBBBBBBB2sBBBBHHHbbbbbbbbbbbbbbbBHHHBBBBBBBBBBBBbbBbHBBB', payload))


def parse_read_params_ext2_cmd(payload: bytes) -> ReadParamsExt2InCmd:
    # noinspection PyProtectedMember
    return ReadParamsExt2InCmd._make(struct.unpack('<BBBBB4sBBBB4sHHHBBBBBBBBBhhhhhhHBBhHHBHHHBBBBBBBBBBBBbBBBBBBBBBBBBbbbbbbbbBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBHBBBBBBBBBBBHb', payload))


def parse_read_params_ext3_cmd(payload: bytes) -> ReadParamsExt3InCmd:
    # noinspection PyProtectedMember
    return ReadParamsExt3InCmd._make(struct.unpack('<', payload))


def parse_realtime_data_3_cmd(payload: bytes) -> RealtimeData3InCmd:
    # noinspection PyProtectedMember
    return RealtimeData3InCmd._make(struct.unpack('<hhhhhhHHB3shhhhhhhhhhhhhhhHHBHBBBBBB', payload))


def parse_realtime_data_4_cmd(payload: bytes) -> RealtimeData4InCmd:
    # noinspection PyProtectedMember
    return RealtimeData4InCmd._make(struct.unpack('<hhhhhhHHB3shhhhhhhhhhhhhhhHHBHBBBBBBhhh1shhhHhhhbbBBhhh30s', payload))


def parse_confirm_cmd(payload: bytes) -> ConfirmInCmd:
    # noinspection PyProtectedMember
    return ConfirmInCmd._make(struct.unpack('<', payload))


def parse_error_cmd(payload: bytes) -> ErrorInCmd:
    # noinspection PyProtectedMember
    return ErrorInCmd._make(struct.unpack('<', payload))


def parse_get_angles_cmd(payload: bytes) -> GetAnglesInCmd:
    # noinspection PyProtectedMember
    return GetAnglesInCmd._make(struct.unpack('<9h', payload))


def parse_get_angles_ext_cmd(payload: bytes) -> GetAnglesExtInCmd:
    # noinspection PyProtectedMember
    return GetAnglesExtInCmd._make(struct.unpack('<', payload))


def parse_read_profile_names_cmd(payload: bytes) \
        -> Optional[ReadProfileNamesInCmd]:
    return None


def parse_i2c_read_reg_buf_cmd(payload: bytes) -> Optional[I2cReadRegBufInCmd]:
    return None


def parse_auto_pid_cmd(payload: bytes) -> Optional[AutoPidInCmd]:
    return None


def parse_debug_vars_info_3_cmd(payload: bytes) \
        -> Optional[DebugVarsInfo3InCmd]:
    return None


def parse_debug_vars_3_cmd(payload: bytes) -> Optional[DebugVars3InCmd]:
    return None


def parse_read_external_data_cmd(payload: bytes) \
        -> Optional[ReadExternalDataInCmd]:
    return None


def parse_set_adj_vars_val_cmd(payload: bytes) -> Optional[SetAdjVarsValInCmd]:
    return None


def parse_read_adj_vars_cfg_cmd(payload: bytes) \
        -> Optional[ReadAdjVarsCfgInCmd]:
    return None


def parse_reset_cmd(payload: bytes) -> Optional[ResetInCmd]:
    return None


def parse_eeprom_read_cmd(payload: bytes) -> Optional[EepromReadInCmd]:
    return None


def parse_calib_info_cmd(payload: bytes) -> Optional[CalibInfoInCmd]:
    return None


def parse_read_file_cmd(payload: bytes) -> Optional[ReadFileInCmd]:
    return None


def parse_script_debug_cmd(payload: bytes) -> Optional[ScriptDebugInCmd]:
    return None


def parse_ahrs_helper_cmd(payload: bytes) -> Optional[AhrsHelperInCmd]:
    return None


def parse_realtime_data_custom_cmd(payload: bytes) \
        -> Optional[RealtimeDataCustomInCmd]:
    return None


def parse_adj_vars_state_cmd(payload: bytes) -> Optional[AdjVarsStateInCmd]:
    return None


def parse_read_rc_inputs_cmd(payload: bytes) -> Optional[ReadRcInputsInCmd]:
    return None


def parse_event_cmd(payload: bytes) -> Optional[EventInCmd]:
    return None


def parse_ext_imu_debug_info_cmd(payload: bytes) \
        -> Optional[ExtImuDebugInfoInCmd]:
    return None


COMMAND_PARSER = {
    CMD_BOARD_INFO: parse_board_info_cmd,
    CMD_BOARD_INFO_3: parse_board_info_3_cmd,
    CMD_READ_PARAMS_3: parse_read_params_3_cmd,
    CMD_READ_PARAMS_EXT: parse_read_params_ext_cmd,
    CMD_READ_PARAMS_EXT2: parse_read_params_ext2_cmd,
    CMD_READ_PARAMS_EXT3: parse_read_params_ext3_cmd,
    CMD_REALTIME_DATA_3: parse_realtime_data_3_cmd,
    CMD_REALTIME_DATA_4: parse_realtime_data_4_cmd,
    CMD_CONFIRM: parse_confirm_cmd,
    CMD_ERROR: parse_error_cmd,
    CMD_GET_ANGLES: parse_get_angles_cmd,
    CMD_GET_ANGLES_EXT: parse_get_angles_ext_cmd,
    CMD_READ_PROFILE_NAMES: parse_read_profile_names_cmd,
    CMD_I2C_READ_REG_BUF: parse_i2c_read_reg_buf_cmd,
    CMD_AUTO_PID: parse_auto_pid_cmd,
    CMD_DEBUG_VARS_INFO_3: parse_debug_vars_info_3_cmd,
    CMD_DEBUG_VARS_3: parse_debug_vars_3_cmd,
    CMD_READ_EXTERNAL_DATA: parse_read_external_data_cmd,
    CMD_SET_ADJ_VARS_VAL: parse_set_adj_vars_val_cmd,
    CMD_READ_ADJ_VARS_CFG: parse_read_adj_vars_cfg_cmd,
    CMD_RESET: parse_reset_cmd,
    CMD_EEPROM_READ: parse_eeprom_read_cmd,
    CMD_CALIB_INFO: parse_calib_info_cmd,
    CMD_READ_FILE: parse_read_file_cmd,
    CMD_SCRIPT_DEBUG: parse_script_debug_cmd,
    CMD_AHRS_HELPER: parse_ahrs_helper_cmd,
    CMD_REALTIME_DATA_CUSTOM: parse_realtime_data_custom_cmd,
    CMD_ADJ_VARS_STATE: parse_adj_vars_state_cmd,
    CMD_READ_RC_INPUTS: parse_read_rc_inputs_cmd,
    CMD_EVENT: parse_event_cmd,
    CMD_EXT_IMU_DEBUG_INFO: parse_ext_imu_debug_info_cmd,
}


def parse_cmd(cmd: RawCmd):
    assert cmd.id in COMMAND_PARSER, 'unknown incoming command: {}'.format(cmd)
    unpack = COMMAND_PARSER.get(cmd.id)
    assert unpack is not None, 'unknown incoming command: {}'.format(cmd)
    return unpack(cmd.payload)
