

class ShareInfo:

    selectPara_dict = {'group': 'A', 'number': 0, 'name': '钻压', 'abbreviation': 'wob'}
    displayPara_dict = {'wob': 0, 'toq': 0, 'rpm': 0, 'accX': 0, 'accY': 0, 'accZ': 0, 'in_pressure': 0,
                             'out_pressure': 0, 'temperature': 0, 'wob_set': 0, 'rpm_set': 0, 'footage': 0,
                             'pump_pressure': 0, 'flow': 0}
    propertyPara_dict = {'k': 1, 'b': 0, 'sample': 1000, 'transparency': 0, 'thickness': 0.5, 'numberDisplay': 0,
                              'gridDisplay': 0}

    para = ['钻压', '扭矩', '转速', '振动X', '振动Y', '振动Z', '内压', '环空压力', '温度']
    para_get_tcp = {'钻压':1, '扭矩':2, '转速':4, '振动X':6, '振动Y':7, '振动Z':8, '内压':9, '环空压力':10, '温度':11}
    para_abbreviations_dict = {'钻压': 'wob', '扭矩': 'toq', '转速': 'rpm', '振动X': 'accX', '振动Y': 'accY', '振动Z': 'accZ',
                               '内压': 'in_pressure', '环空压力': 'out_pressure', '温度': 'temperature'}
    para_Peripheral = ['施工钻压', '施工转速', '进尺', '泵压', '流量']
    paraPeripheral_get_NI_ai_count ={'施工钻压': 0, '施工转速': 1, '进尺': 2, '泵压': 3,
                                         '流量': 4}
    paraPeripheral_abbreviations_dict = {'施工钻压': 'wob_set', '施工转速': 'rpm_set', '进尺': 'footage', '泵压': 'pump_pressure',
                                         '流量': 'flow'}
    subWinTable = {} #子窗口


    """
    NI DAQmx
    USB-6210
    """
    physicalChannel = 'Dev2/ai0:3'
    maxVoltage = 10
    minVoltage = 0
    sampleRate =1000
    numberOfSamples = 1000# Have to share number of samples with runTask
    ni_vals = []
    ni_isConnect = False

    do_port = "Dev2/port0/line0"

    """
    TCP
    192.168.1.1:8899
    """
    tcp_vals = None
    tcp_isRecv = False
    tcp_isConnect = False  # 是否TCP连接


    """
    time
    """
    time_start = None
    time_now = None
    time_end = None

