import os
import time
import argparse
import tensorflow as tf
from sampler import WarpSampler
from model import Model
#from tqdm import tqdm
from util import *
import traceback


def str2bool(s):
    if s not in {'False', 'True'}:
        raise ValueError('Not a valid boolean string')
    return s == 'True'

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', required=True)
    parser.add_argument('--batch_size', default=128, type=int)
    parser.add_argument('--lr', default=0.001, type=float)
    parser.add_argument('--maxlen', default=50, type=int)
    parser.add_argument('--hidden_units', default=100, type=int)
    parser.add_argument('--num_blocks', default=2, type=int)
    parser.add_argument('--num_epochs', default=401, type=int)
    parser.add_argument('--num_heads', default=1, type=int)
    parser.add_argument('--dropout_rate', default=0.5, type=float)
    parser.add_argument('--l2_emb', default=0.0, type=float)
    args = parser.parse_args()

    '''
    if not os.path.isdir('files/' + args.dataset):
        os.makedirs('files/' + args.dataset)
    with open(os.path.join('files', args.dataset, 'args.txt'), 'w') as f:
        f.write('\n'.join([str(k) + ',' + str(v) for k, v in sorted(vars(args).items(), key=lambda x: x[0])]))
    f.close()
    '''
    print()
    print(str(args))
    print()

    dataset = data_partition(args.dataset)
    [user_train, user_valid, user_test, usernum, itemnum] = dataset
    num_batch = len(user_train) // args.batch_size
    cc = 0.0
    for u in user_train:
        cc += len(user_train[u])
    print('average sequence length: %.2f' % (cc / len(user_train)))

    #f = open(os.path.join('files', args.dataset, 'log.txt'), 'w')
    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True
    config.allow_soft_placement = True
    sess = tf.Session(config=config)

    sampler = WarpSampler(user_train, usernum, itemnum, batch_size=args.batch_size, maxlen=args.maxlen, n_workers=3)
    model = Model(usernum, itemnum, args)
    sess.run(tf.initialize_all_variables())

    T = 0.0
    t0 = time.time()
    bmap_, bhr_5, bhr_10, bndcg_5, bndcg_10, bepoch, bT, btest = 0, 0, 0, 0, 0, 0, 0, []

    try:
        for epoch in range(1, args.num_epochs + 1):
            #for step in tqdm(range(num_batch), total=num_batch, ncols=70, leave=False, unit='b'):
            for step in range(num_batch):
                u, seq, pos, neg = sampler.next_batch()
                auc, loss, _ = sess.run([model.auc, model.loss, model.train_op],
                                        {model.u: u, model.input_seq: seq, model.pos: pos, model.neg: neg,
                                         model.is_training: True})

            if epoch % 20 == 0:
                t1 = time.time() - t0
                T += t1
                print('Evaluating')
                t_test = evaluate(model, dataset, args, sess)
                t_valid = evaluate_valid(model, dataset, args, sess)
                print('epoch:%d, time: %f s, (valid) MAP: %.4f, HR@5: %.4f, HR@10: %.4f, NDCG@5: %.4f, NDCG@10: %.4f, (test) MAP: %.4f, HR@5: %.4f, HR@10: %.4f, NDCG@5: %.4f, NDCG@10: %.4f\n' % (
                epoch, T, t_valid[0], t_valid[1], t_valid[2], t_valid[3], t_valid[4], t_test[0], t_test[1], t_test[2], t_test[3], t_test[4]))

                if int(t_valid[0] >= bmap_) + int(t_valid[1] >= bhr_5) + int(t_valid[2] >= bhr_10) + int(t_valid[3] >= bndcg_5) + int(t_valid[4] >= bndcg_10) >= 4:
                    bmap_, bhr_5, bhr_10, bndcg_5, bndcg_10, bepoch, bT, btest = t_valid[0], t_valid[1], t_valid[2], t_valid[3], t_valid[4], epoch, T, t_test
                if epoch - bepoch >= 60:
                    print('\nepoch:%d, time: %f s, (valid) MAP: %.4f, HR@5: %.4f, HR@10: %.4f, NDCG@5: %.4f, NDCG@10: %.4f, (test) MAP: %.4f, HR@5: %.4f, HR@10: %.4f, NDCG@5: %.4f, NDCG@10: %.4f\n' % 
                          (bepoch, bT, bmap_, bhr_5, bhr_10, bndcg_5, bndcg_10, btest[0], btest[1], btest[2], btest[3], btest[4]))
                    break

                #f.write(str(t_valid) + ' ' + str(t_test) + '\n')
                #f.flush()
                t0 = time.time()
    except:
        traceback.print_exc()
        sampler.close()
        #f.close()
        exit(1)

    #f.close()
    sampler.close()
    print("Done")
