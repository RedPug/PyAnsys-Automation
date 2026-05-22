import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

filename = './solver_inputs/trial_temp_0_conv_0.csv'
df = pd.read_csv(filename)

fig, ax1 = plt.subplots()

ax1.set_xlabel('Time (s)')
ax1.set_ylabel('Temperature (°C)')
ax1.set_title('Temperature Time Series with Noise Layers')



temp_input_sampled = np.interp(df['time'], df['temp_curve_time'], df['temp_curve_temp'])

ax1.plot(df['temp_curve_time'], df['temp_curve_temp'], label='Input Curve', color='red', linestyle='solid')


i = 0
while 'temp_noise' + str(i) in df:
    ax1.plot(df['time'], df['temp_noise' + str(i)] + temp_input_sampled, label='Noise Layer ' + str(i), linestyle='dashed', alpha=0.7)
    i += 1

ax1.plot(df['time'], df['temp'], label='Result', color='k', linestyle='solid')

ax1.legend()

plt.show()