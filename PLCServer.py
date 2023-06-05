# Import required libraries
from pymodbus.server import StartTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
from random import randrange, sample

# Define your device identification
device_identification = ModbusDeviceIdentification()
device_identification.VendorName  = 'ModbusTagServer'
device_identification.ProductCode = 'pymodbus'
device_identification.VendorUrl   = 'Pymodbus.com'
device_identification.ProductName = 'pymodbus Server'
device_identification.ModelName   = 'pymodbus Server'
device_identification.MajorMinorRevision = '1.0'

# Create a function to generate a list with 10000 addresses and 10 random values
def create_data_store(value_range):
    data_store = [0 for _ in range(10000)]
    for i in sample(range(10000), 10):
        data_store[i] = randrange(value_range)
    return data_store

# Create data stores and populate them with random values
coil_store = ModbusSequentialDataBlock(0, create_data_store(2))
di_store = ModbusSequentialDataBlock(0, create_data_store(2))
hr_store = ModbusSequentialDataBlock(0, create_data_store(65535))
ir_store = ModbusSequentialDataBlock(0, create_data_store(65535))

# Create slave context
slave_context = ModbusSlaveContext(
    di=di_store,
    co=coil_store,
    hr=hr_store,
    ir=ir_store,
    zero_mode=True
)

# Create server context
server_context = ModbusServerContext(slaves=slave_context, single=True)

# Start the server
StartTcpServer(context=server_context, identity=device_identification)
