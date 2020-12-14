import sys
sys.path.append("../")
sys.path.append("AIF360/")
import numpy as np
from fairness_metrics.tot_metrics import TPR, TNR
from aif360.metrics import BinaryLabelDatasetMetric
from aif360.algorithms.preprocessing.optim_preproc import OptimPreproc
from aif360.algorithms.preprocessing.optim_preproc_helpers.opt_tools\
    import OptTools
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score
from aif360.datasets import StandardDataset
import warnings
import pandas as pd
from sklearn.model_selection import train_test_split
warnings.simplefilter("ignore")


def get_distortion_adult(vold, vnew):
    """Distortion function for the adult dataset. We set the distortion
    metric here. See section 4.3 in supplementary material of
    http://papers.nips.cc/paper/6988-optimized-pre-processing-for-discrimination-prevention
    for an example

    Note:
        Users can use this as templates to create other distortion functions.

    Args:
        vold (dict) : {attr:value} with old values
        vnew (dict) : dictionary of the form {attr:value} with new values

    Returns:
        d (value) : distortion value
    """

    # Define local functions to adjust education and age
    def adjustEdu(v):
        if v == '>12':
            return 13
        elif v == '<6':
            return 5
        else:
            return int(v)

    def adjustAge(a):
        if a == '>=70':
            return 70.0
        else:
            return float(a)

    def adjustInc(a):
        if a == "<=50K":
            return 0
        elif a == ">50K":
            return 1
        else:
            return int(a)

    # value that will be returned for events that should not occur
    bad_val = 3.0

    # Adjust education years
    eOld = adjustEdu(vold['Education Years'])
    eNew = adjustEdu(vnew['Education Years'])

    # Education cannot be lowered or increased in more than 1 year
    if (eNew < eOld) | (eNew > eOld + 1):
        return bad_val

    # adjust age
    aOld = adjustAge(vold['Age (decade)'])
    aNew = adjustAge(vnew['Age (decade)'])

    # Age cannot be increased or decreased in more than a decade
    if np.abs(aOld - aNew) > 10.0:
        return bad_val

    # Penalty of 2 if age is decreased or increased
    if np.abs(aOld - aNew) > 0:
        return 2.0

    # Adjust income
    incOld = adjustInc(vold['Income Binary'])
    incNew = adjustInc(vnew['Income Binary'])

    # final penalty according to income
    if incOld > incNew:
        return 1.0
    else:
        return 0.0


default_mappings = {
    'label_maps': [{1.0: '>50K', 0.0: '<=50K'}],
    'protected_attribute_maps': [{1.0: 'White', 0.0: 'Non-white'},
                                 {1.0: 'Male', 0.0: 'Female'}]
}


class AdultDataset_test(StandardDataset):
    """Adult Census Income Dataset.

    See :file:`aif360/data/raw/adult/README.md`.
    """

    def __init__(
            self,
            label_name='income-per-year',
            favorable_classes=[
                '>50K',
                '>50K.'],
            protected_attribute_names=[
                'race',
                'sex'],
            privileged_classes=[
                ['White'],
                ['Male']],
            instance_weights_name=None,
            categorical_features=[
                'workclass',
                'education',
                'marital-status',
                'occupation',
                'relationship',
                'native-country'],
            features_to_keep=[],
            features_to_drop=['fnlwgt'],
            na_values=['?'],
            custom_preprocessing=None,
            metadata=default_mappings):

        test_path = 'AIF360/aif360/data/raw/adult/adult.test'
        # as given by adult.names
        column_names = [
            'age',
            'workclass',
            'fnlwgt',
            'education',
            'education-num',
            'marital-status',
            'occupation',
            'relationship',
            'race',
            'sex',
            'capital-gain',
            'capital-loss',
            'hours-per-week',
            'native-country',
            'income-per-year']

        test = pd.read_csv(test_path, header=0, names=column_names,
                           skipinitialspace=True, na_values=na_values)

        df = test

        super(
            AdultDataset_test,
            self).__init__(
            df=df,
            label_name=label_name,
            favorable_classes=favorable_classes,
            protected_attribute_names=protected_attribute_names,
            privileged_classes=privileged_classes,
            instance_weights_name=instance_weights_name,
            categorical_features=categorical_features,
            features_to_keep=features_to_keep,
            features_to_drop=features_to_drop,
            na_values=na_values,
            custom_preprocessing=custom_preprocessing,
            metadata=metadata)


def load_preproc_data_adult(protected_attributes=None):
    def custom_preprocessing(df):
        """The custom pre-processing function is adapted from
            https://github.com/fair-preprocessing/nips2017/blob/master/Adult/code/Generate_Adult_Data.ipynb
        """
        np.random.seed(1)
        # Group age by decade
        df['Age (decade)'] = df['age'].apply(lambda x: x // 10 * 10)
        # df['Age (decade)'] = df['age'].apply(lambda x: np.floor(x/10.0)*10.0)

        def group_edu(x):
            if x == -1:
                return 'missing_edu'
            elif x <= 5:
                return '<6'
            elif x >= 13:
                return '>12'
            else:
                return x

        def age_cut(x):
            if x >= 70:
                return '>=70'
            else:
                return x

        def group_race(x):
            if x == "White":
                return 1.0
            else:
                return 0.0

        # Cluster education and age attributes.
        # Limit education range
        df['Education Years'] = df['education-num'].apply(
            lambda x: group_edu(x))
        df['Education Years'] = df['Education Years'].astype('category')

        # Limit age range
        df['Age (decade)'] = df['Age (decade)'].apply(lambda x: age_cut(x))

        # Rename income variable
        df['Income Binary'] = df['income-per-year']

        # Recode sex and race
        df['sex'] = df['sex'].replace({'Female': 0.0, 'Male': 1.0})
        df['race'] = df['race'].apply(lambda x: group_race(x))

        return df

    XD_features = ['Age (decade)', 'Education Years', 'sex', 'race']
    D_features = [
        'sex',
        'race'] if protected_attributes is None else protected_attributes
    Y_features = ['Income Binary']
    X_features = list(set(XD_features) - set(D_features))
    categorical_features = ['Age (decade)', 'Education Years']

    # privileged classes
    all_privileged_classes = {"sex": [1.0],
                              "race": [1.0]}

    # protected attribute maps
    all_protected_attribute_maps = {"sex": {1.0: 'Male', 0.0: 'Female'},
                                    "race": {1.0: 'White', 0.0: 'Non-white'}}

    return AdultDataset_test(
        label_name=Y_features[0],
        favorable_classes=['>50K', '>50K.'],
        protected_attribute_names=D_features,
        privileged_classes=[all_privileged_classes[x] for x in D_features],
        instance_weights_name=None,
        categorical_features=categorical_features,
        features_to_keep=X_features + Y_features + D_features,
        na_values=['?'],
        metadata={'label_maps': [{1.0: '>50K', 0.0: '<=50K'}],
                  'protected_attribute_maps': [all_protected_attribute_maps[x]
                                               for x in D_features]},
        custom_preprocessing=custom_preprocessing)


dataset_orig_vt = load_preproc_data_adult(['sex'])


class AdultDataset_train(StandardDataset):
    """Adult Census Income Dataset.

    See :file:`aif360/data/raw/adult/README.md`.
    """

    def __init__(
            self,
            label_name='income-per-year',
            favorable_classes=[
                '>50K',
                '>50K.'],
            protected_attribute_names=[
                'race',
                'sex'],
            privileged_classes=[
                ['White'],
                ['Male']],
            instance_weights_name=None,
            categorical_features=[
                'workclass',
                'education',
                'marital-status',
                'occupation',
                'relationship',
                'native-country'],
            features_to_keep=[],
            features_to_drop=['fnlwgt'],
            na_values=['?'],
            custom_preprocessing=None,
            metadata=default_mappings):

        train_path = 'AIF360/aif360/data/raw/adult/adult.data'
        # as given by adult.names
        column_names = [
            'age',
            'workclass',
            'fnlwgt',
            'education',
            'education-num',
            'marital-status',
            'occupation',
            'relationship',
            'race',
            'sex',
            'capital-gain',
            'capital-loss',
            'hours-per-week',
            'native-country',
            'income-per-year']

        train = pd.read_csv(train_path, header=None, names=column_names,
                            skipinitialspace=True, na_values=na_values)

        df = train
        df_neg = df.loc[df['income-per-year'] == '<=50K', :]
        df_neg_priv = df_neg.loc[(
            df_neg['income-per-year'] == '<=50K') & (df_neg['sex'] == 'Male'), :]
        df_neg_unpriv = df_neg.loc[(
            df_neg['income-per-year'] == '<=50K') & (df_neg['sex'] != 'Male'), :]

        _, df_neg_priv_test = train_test_split(
            df_neg_priv, test_size=4650, random_state=17)
        _, df_neg_unpriv_test = train_test_split(
            df_neg_unpriv, test_size=2850, random_state=17)
        df_neg_test = df_neg_priv_test.append(df_neg_unpriv_test)
        print('negative outcome, unpriv')
        print(len(df_neg_unpriv_test.index))
        print('negative outcome, priv')
        print(len(df_neg_priv_test.index))

        df_pos = df.loc[df['income-per-year'] == '>50K', :]
        df_pos_priv = df_pos.loc[(
            df_pos['income-per-year'] == '>50K') & (df_pos['sex'] == 'Male'), :]
        df_pos_unpriv = df_pos.loc[(
            df_pos['income-per-year'] == '>50K') & (df_pos['sex'] != 'Male'), :]
        _, df_pos_priv_test = train_test_split(
            df_pos_priv, test_size=1800, random_state=17)
        _, df_pos_unpriv_test = train_test_split(
            df_pos_unpriv, test_size=700, random_state=17)
        df_pos_test = df_pos_priv_test.append(df_pos_unpriv_test)
        df = df_pos_test.append(df_neg_test)
        print('positive outcome, unpriv')
        print(len(df_pos_unpriv_test.index))
        print('positive outcome, priv')
        print(len(df_pos_priv_test.index))

        super(
            AdultDataset_train,
            self).__init__(
            df=df,
            label_name=label_name,
            favorable_classes=favorable_classes,
            protected_attribute_names=protected_attribute_names,
            privileged_classes=privileged_classes,
            instance_weights_name=instance_weights_name,
            categorical_features=categorical_features,
            features_to_keep=features_to_keep,
            features_to_drop=features_to_drop,
            na_values=na_values,
            custom_preprocessing=custom_preprocessing,
            metadata=metadata)


def train_before_resample():
    privileged_groups = [{'sex': 1}]
    unprivileged_groups = [{'sex': 0}]
    dataset_orig_train = load_preproc_data_adult(['sex'])

    optim_options = {
        "distortion_fun": get_distortion_adult,
        "epsilon": 0.05,
        "clist": [0.99, 1.99, 2.99],
        "dlist": [.1, 0.05, 0]
    }

    OP = OptimPreproc(OptTools, optim_options,
                      unprivileged_groups=unprivileged_groups,
                      privileged_groups=privileged_groups)

    OP = OP.fit(dataset_orig_train)

    dataset_transf_cat_test = OP.transform(dataset_orig_vt, transform_Y=True)
    dataset_transf_cat_test = dataset_orig_vt.align_datasets(
        dataset_transf_cat_test)

    dataset_transf_cat_train = OP.transform(
        dataset_orig_train, transform_Y=True)
    dataset_transf_cat_train = dataset_orig_train.align_datasets(
        dataset_transf_cat_train)

    scale_transf = StandardScaler()
    X_train = dataset_orig_train.features
    y_train = dataset_orig_train.labels.ravel()
    X_test = scale_transf.fit_transform(dataset_orig_vt.features)
    lmod = LogisticRegression()
    lmod.fit(X_train, y_train)
    y_pred = lmod.predict(X_test)
    print('Accuracy and fairness results before resampling')
    print('accuracy')
    print(accuracy_score(dataset_orig_vt.labels, y_pred))
    dataset_orig_vt_copy = dataset_orig_vt.copy()
    dataset_orig_vt_copy.labels = y_pred
    metric_transf_train = BinaryLabelDatasetMetric(
        dataset_orig_vt_copy,
        unprivileged_groups=unprivileged_groups,
        privileged_groups=privileged_groups)

    print('p-rule')
    print(min(metric_transf_train.disparate_impact(),
              1 / metric_transf_train.disparate_impact()))
    print('FPR for priv')
    orig_sens_att = dataset_orig_vt.protected_attributes.ravel()
    print(1 - TNR(dataset_orig_vt.labels.ravel()
                  [orig_sens_att == 0], y_pred[orig_sens_att == 0], 1))
    print("FNR for priv")
    print(1 - TPR(dataset_orig_vt.labels.ravel()
                  [orig_sens_att == 0], y_pred[orig_sens_att == 0], 1))
    print('FPR for unpriv')
    orig_sens_att = dataset_orig_vt.protected_attributes.ravel()
    print(1 - TNR(dataset_orig_vt.labels.ravel()
                  [orig_sens_att == 1], y_pred[orig_sens_att == 1], 1))
    print("FNR for unpriv")
    print(1 - TPR(dataset_orig_vt.labels.ravel()
                  [orig_sens_att == 1], y_pred[orig_sens_att == 1], 1))


if __name__ == "__main__":
    train_before_resample()
