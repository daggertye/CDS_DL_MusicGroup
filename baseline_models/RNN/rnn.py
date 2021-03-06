import tensorflow as tf
import numpy as np
import pretty_midi
import random
import librosa.display

SAMPLE_FRQ = 10

START_POINT = 1000
TRAIN_LENGTH = 1000
TRAINING_ECHO = 100

NUM_STEPS = 10
MAX_CONCURRENT_NOTES = 3
GENERATE_LENGTH = 1000

input = 'EspanjaTango.mid'
output = 'out.mid'
prompt = 10

# Loading data
pm = pretty_midi.PrettyMIDI(input)
fs = SAMPLE_FRQ
def plot_piano_roll(pm, start_pitch, end_pitch, fs=fs):
    # Use librosa's specshow function for displaying the piano roll
    librosa.display.specshow(pm.get_piano_roll(fs)[start_pitch:end_pitch],
                             hop_length=1, sr=fs, x_axis='time', y_axis='cqt_note',
                             fmin=pretty_midi.note_number_to_hz(start_pitch))


# plt.figure(figsize=(12, 4))
# plot_piano_roll(pm, 24, 84)

roll = np.ndarray.transpose(pm.get_piano_roll(SAMPLE_FRQ))

train_roll = roll[START_POINT:START_POINT + TRAIN_LENGTH]
print(train_roll.shape)
note_size = train_roll.shape[1]
print("note size " + str(note_size))



# predict based on num_steps notes before
num_steps = NUM_STEPS

batch_size = 1

x = tf.placeholder(tf.float32, [batch_size, num_steps, note_size])
y = tf.placeholder(tf.float32, [batch_size, num_steps, note_size])

x_inputs = tf.unstack(x, axis=1)
y_outputs = tf.unstack(y, axis=1)


state_size = 128

with tf.variable_scope('rnn_cell_1'):
    W_xh = tf.get_variable('W_xh', [note_size, state_size])
    W_hh = tf.get_variable('W_hh', [state_size, state_size])
    b_h = tf.get_variable('b_h', [state_size])

def rnn_cell(rnn_input, prev_state, scope):
    with tf.variable_scope(scope, reuse=True):
        W_xh = tf.get_variable('W_xh',
                               [rnn_input.get_shape().as_list()[1], state_size])
        W_hh = tf.get_variable('W_hh', [state_size, state_size])
        b_h = tf.get_variable('b_h', [state_size])
        return tf.tanh(
            tf.matmul(prev_state, W_hh) + tf.nn.xw_plus_b(rnn_input, W_xh, b_h))



init_state = tf.zeros([batch_size, state_size])
state = init_state

result = []
for rnn_input in x_inputs:
    state = rnn_cell(rnn_input, state, 'rnn_cell_1')
    result.append(state)


with tf.variable_scope('softmax'):
    W_hy = tf.get_variable('W_hy', [state_size,note_size])
    b_y = tf.get_variable('b_y', [note_size])

logits = [tf.nn.xw_plus_b(state, W_hy, b_y) for state in result]
preds = [tf.nn.softmax(logit) for logit in logits]


losses = [tf.nn.softmax_cross_entropy_with_logits_v2(labels=label, logits=logit)
          for label, logit in zip(y_outputs, logits)]

total_loss = tf.reduce_mean(losses)
train_step = tf.train.AdamOptimizer(learning_rate=0.01).minimize(total_loss)





# training


data = ([], [])

for i in range(len(train_roll) - num_steps - 2):
    train_x = train_roll[i: i + num_steps]
    train_y = train_roll[i + 1: i + num_steps + 1]
    data[0].append(train_x)
    data[1].append(train_y)


data = (np.array(data[0], dtype=float), np.array(data[1], dtype=float))
data_train = np.hstack(data)

sess = tf.InteractiveSession()
init = tf.global_variables_initializer()
sess.run(init)

max_epochs = TRAINING_ECHO

for i in range(max_epochs):
    print(i)
    np.random.shuffle(data_train)
    for j in range(data_train.shape[0] // batch_size):
        start, end = j * batch_size, (j + 1) * batch_size
        x_batch, y_batch = data_train[start:end, :num_steps], data_train[start:end, num_steps:]
        sess.run(train_step, feed_dict={x: x_batch, y: y_batch})



# generate music

n = MAX_CONCURRENT_NOTES

def generate_music(t, prompt):
    default = tf.zeros( [batch_size, num_steps, note_size])
    current = prompt[0:num_steps].tolist()
    for i in range(t):
        print("compare "+str(current[-2]) + " " + str(current[-1]))
        if current[-2] == current[-1] and current[-3] == current[-2] :

            v = np.array(current[-1]).max()
            selected = np.random.choice(128,3)
            print("random " + str(selected))
            p = [0.0] * 128
            for s in selected:
                p[s] = v
            current.append(p)
        else :
            x_batch = [current[i:i+num_steps]]
            result = sess.run(preds, feed_dict={x: x_batch, y: default.eval()})
            p = np.squeeze(result)[0]
            selected = np.argsort(p)[-5:-1]
            p[np.argsort(p)[:-5]] = 0.0
            print("the note selected for " + str(i) + " is " + str(selected))
            current.append(p.tolist())

    return current


gen = generate_music(GENERATE_LENGTH, roll[START_POINT:START_POINT + prompt])
print("the length of generated file is " + str(len(gen)))


pm_gen = pretty_midi.PrettyMIDI(initial_tempo=80)

instrument = pretty_midi.Instrument(program=pm.instruments[0].program, is_drum=False, name='my ins')


for t in range(len(gen)):
    for i in range(128):
        v = gen[t][i]
        if v > 0.0 :
            print(str(t/fs) + " " + str((t+1)/fs))
            note = pretty_midi.Note(velocity=(int)(v), pitch=i, start=t/fs, end=(t + 1)/fs)
            instrument.notes.append(note)


pm_gen.instruments.append(instrument)

pm_gen.write(output)

