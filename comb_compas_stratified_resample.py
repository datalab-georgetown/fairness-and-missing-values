import sys
sys.path.append("../")
sys.path.append("AIF360/")
# import warnings
# from sklearn.model_selection import train_test_split
# from aif360.datasets import StandardDataset
# import pandas as pd
# import os
# from sklearn.utils import resample
# import sklearn
# import matplotlib.pyplot as plt
# from IPython.display import Markdown, display
# from sklearn.metrics import accuracy_score
# from sklearn.preprocessing import StandardScaler
# from sklearn.linear_model import LogisticRegression
# from sklearn import tree
# from common_utils import compute_metrics
# from aif360.algorithms.preprocessing.optim_preproc_helpers.opt_tools import OptTools
# from aif360.algorithms.preprocessing.optim_preproc_helpers.distortion_functions\
#     import get_distortion_adult, get_distortion_german, get_distortion_compas
# from aif360.algorithms.preprocessing.optim_preproc_helpers.data_preproc_functions\
#     import load_preproc_data_adult, load_preproc_data_german
# from aif360.algorithms.preprocessing.optim_preproc import OptimPreproc
# from aif360.metrics.utils import compute_boolean_conditioning_vector
# from aif360.metrics import ClassificationMetric
# from aif360.metrics import BinaryLabelDatasetMetric
# from aif360.datasets import AdultDataset, GermanDataset
# from aif360.datasets import BinaryLabelDataset
# from fairness_metrics.tot_metrics import TPR, TNR, get_BCR, DIbinary
# from tqdm import tqdm
# import numpy as np

import warnings
from sklearn.model_selection import train_test_split
from aif360.datasets import StandardDataset
import pandas as pd
from sklearn.metrics import accuracy_score
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from aif360.algorithms.preprocessing.optim_preproc_helpers.opt_tools import OptTools
from aif360.algorithms.preprocessing.optim_preproc import OptimPreproc
from aif360.metrics import BinaryLabelDatasetMetric
from fairness_metrics.tot_metrics import TPR, TNR
import numpy as np
from sklearn.utils import resample
warnings.simplefilter("ignore")
np.random.seed(10)


def get_distortion_compas(vold, vnew):
    """Distortion function for the compas dataset. We set the distortion
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
    # Distortion cost
    distort = {}
    distort['two_year_recid'] = pd.DataFrame(
        {'No recid.': [0., 2.],
         'Did recid.': [2., 0.]},
        index=['No recid.', 'Did recid.'])
    distort['age_cat'] = pd.DataFrame(
        {'Less than 25': [0., 1., 2.],
         '25 to 45': [1., 0., 1.],
         'Greater than 45': [2., 1., 0.]},
        index=['Less than 25', '25 to 45', 'Greater than 45'])
#    distort['length_of_stay'] = pd.DataFrame(
#                            {'<week':    [0., 1., 2.],
#                            '<3months':  [1., 0., 1.],
#                            '>3 months': [2., 1., 0.]},
#                            index=['<week', '<3months', '>3 months'])
    distort['c_charge_degree'] = pd.DataFrame(
        {'M': [0., 2.],
         'F': [1., 0.]},
        index=['M', 'F'])
    distort['priors_count'] = pd.DataFrame(
        {'0': [0., 1., 2., 100.],
         '1 to 3': [1., 0., 1., 100.],
         'More than 3': [2., 1., 0., 100.],
         'missing': [0., 0., 0., 1.]},
        index=['0', '1 to 3', 'More than 3', 'missing'])
#    distort['score_text'] = pd.DataFrame(
#                                {'Low':     [0., 2.,100.],
#                                'MediumHigh':     [2., 0.,100.],
#                                'missing score':  [0., 0.,1.]},
#                                index=['Low', 'MediumHigh','missing score'])

    distort['score_text'] = pd.DataFrame(
        {'Low': [0., 2.],
         'MediumHigh': [2., 0.]},
        index=['Low', 'MediumHigh'])
    distort['sex'] = pd.DataFrame(
        {0.0: [0., 2.],
         1.0: [2., 0.]},
        index=[0.0, 1.0])
    distort['race'] = pd.DataFrame(
        {0.0: [0., 2.],
         1.0: [2., 0.]},
        index=[0.0, 1.0])

    total_cost = 0.0
    for k in vold:
        if k in vnew:
            total_cost += distort[k].loc[vnew[k], vold[k]]

    return total_cost


default_mappings = {
    'label_maps': [{1.0: 'Did recid.', 0.0: 'No recid.'}],
    'protected_attribute_maps': [{0.0: 'Male', 1.0: 'Female'},
                                 {1.0: 'Caucasian', 0.0: 'Not Caucasian'}]
}


def default_preprocessing(df):
    """Perform the same preprocessing as the original analysis:
    https://github.com/propublica/compas-analysis/blob/master/Compas%20Analysis.ipynb
    """
    return df[(df.days_b_screening_arrest <= 30)
              & (df.days_b_screening_arrest >= -30)
              & (df.is_recid != -1)
              & (df.c_charge_degree != 'O')
              & (df.score_text != 'N/A')]


class CompasDataset_test(StandardDataset):
    """ProPublica COMPAS Dataset.

    See :file:`aif360/data/raw/compas/README.md`.
    """

    def __init__(
            self,
            label_name='two_year_recid',
            favorable_classes=[0],
            protected_attribute_names=[
                'sex',
                'race'],
            privileged_classes=[
                ['Female'],
                ['Caucasian']],
            instance_weights_name=None,
            categorical_features=[
                'age_cat',
                'c_charge_degree',
                'c_charge_desc'],
            features_to_keep=[
                'sex',
                'age',
                'age_cat',
                'race',
                'juv_fel_count',
                'juv_misd_count',
                'juv_other_count',
                'priors_count',
                'c_charge_degree',
                'c_charge_desc',
                'two_year_recid',
                'length_of_stay'],
            features_to_drop=[],
            na_values=[],
            custom_preprocessing=default_preprocessing,
            metadata=default_mappings):
        """See :obj:`StandardDataset` for a description of the arguments.

        Note: The label value 0 in this case is considered favorable (no
        recidivism).

        Examples:
            In some cases, it may be useful to keep track of a mapping from
            `float -> str` for protected attributes and/or labels. If our use
            case differs from the default, we can modify the mapping stored in
            `metadata`:

            >>> label_map = {1.0: 'Did recid.', 0.0: 'No recid.'}
            >>> protected_attribute_maps = [{1.0: 'Male', 0.0: 'Female'}]
            >>> cd = CompasDataset(protected_attribute_names=['sex'],
            ... privileged_classes=[['Male']], metadata={'label_map': label_map,
            ... 'protected_attribute_maps': protected_attribute_maps})

            Now this information will stay attached to the dataset and can be
            used for more descriptive visualizations.
        """
        np.random.seed(1)

        def quantizePrior1(x):
            if x <= 0:
                return 0
            elif 1 <= x <= 3:
                return 1
            else:
                return 2

        def quantizeLOS(x):
            if x <= 7:
                return 0
            if 8 < x <= 93:
                return 1
            else:
                return 2

        def group_race(x):
            if x == "Caucasian":
                return 1.0
            else:
                return 0.0

        filepath = 'compas-test.csv'
        df = pd.read_csv(filepath, index_col='id', na_values=[])

        df['age_cat'] = df['age_cat'].replace('Greater than 45', 2)
        df['age_cat'] = df['age_cat'].replace('25 - 45', 1)
        df['age_cat'] = df['age_cat'].replace('Less than 25', 0)
        df['score_text'] = df['score_text'].replace('High', 1)
        df['score_text'] = df['score_text'].replace('Medium', 1)
        df['score_text'] = df['score_text'].replace('Low', 0)
        df['priors_count'] = df['priors_count'].apply(
            lambda x: quantizePrior1(x))
        df['length_of_stay'] = (pd.to_datetime(df['c_jail_out']) -
                                pd.to_datetime(df['c_jail_in'])).apply(
            lambda x: x.days)
        df['length_of_stay'] = df['length_of_stay'].apply(
            lambda x: quantizeLOS(x))
        df = df.loc[~df['race'].isin(
            ['Native American', 'Hispanic', 'Asian', 'Other']), :]
        df['c_charge_degree'] = df['c_charge_degree'].replace({'F': 0, 'M': 1})

        df1 = df[['priors_count', 'c_charge_degree', 'race',
                  'age_cat', 'score_text', 'two_year_recid']]

        tot = []
        for index, row in df1.iterrows():
            result = ''
            for j in df1.columns:
                result = result + str(row[j])
            tot.append(result)
        df1['tmp_feature'] = tot
        df1['mis_prob'] = 0
        for i in df1['tmp_feature'].unique():
            if 'African' in i and i[-1] == '0' and i[0] == '0':
                df1.loc[df1['tmp_feature'] == i, 'mis_prob'] = 0.8
            elif 'African' in i and i[0] == '2':
                df1.loc[df1['tmp_feature'] == i, 'mis_prob'] = 0.2
            else:
                df1.loc[df1['tmp_feature'] == i, 'mis_prob'] = 0.05
        new_label = []
        for i, j in zip(df1['mis_prob'], df1['priors_count']):
            if np.random.binomial(1, i, 1)[0] == 1:
                new_label.append(3)
            else:
                new_label.append(j)
        df['priors_count'] = new_label

        df['c_charge_degree'] = df['c_charge_degree'].replace({0: 'F', 1: 'M'})

        super(
            CompasDataset_test,
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


def load_preproc_data_compas(protected_attributes=None):
    def custom_preprocessing(df):
        """The custom pre-processing function is adapted from
            https://github.com/fair-preprocessing/nips2017/blob/master/compas/code/Generate_Compas_Data.ipynb
        """

        df = df[['age',
                 'c_charge_degree',
                 'race',
                 'age_cat',
                 'score_text',
                 'sex',
                 'priors_count',
                 'days_b_screening_arrest',
                 'decile_score',
                 'is_recid',
                 'two_year_recid',
                 'length_of_stay']]

        # Indices of data samples to keep
        ix = df['days_b_screening_arrest'] <= 30
        ix = (df['days_b_screening_arrest'] >= -30) & ix
        ix = (df['is_recid'] != -1) & ix
        ix = (df['c_charge_degree'] != "O") & ix
        ix = (df['score_text'] != 'N/A') & ix
        df = df.loc[ix, :]

        # Restrict races to African-American and Caucasian
        dfcut = df.loc[~df['race'].isin(
            ['Native American', 'Hispanic', 'Asian', 'Other']), :]

        # Restrict the features to use
        dfcutQ = dfcut[['sex',
                        'race',
                        'age_cat',
                        'c_charge_degree',
                        'score_text',
                        'priors_count',
                        'is_recid',
                        'two_year_recid',
                        'length_of_stay']].copy()

        # Quantize priors count between 0, 1-3, and >3
        def quantizePrior(x):
            if x == 0:
                return '0'
            elif x == 1:
                return '1 to 3'
            elif x == 2:
                return 'More than 3'
            else:
                return 'missing'
        # Quantize length of stay

        def quantizeLOS(x):
            if x == 0:
                return '<week'
            if x == 1:
                return '<3months'
            else:
                return '>3 months'

        # Quantize length of stay
        def adjustAge(x):
            if x == 1:
                return '25 to 45'
            elif x == 2:
                return 'Greater than 45'
            elif x == 0:
                return 'Less than 25'
        # Quantize score_text to MediumHigh

        def quantizeScore(x):
            if x == 1:
                return 'MediumHigh'
            else:
                return 'Low'

        def group_race(x):
            if x == "Caucasian":
                return 1.0
            else:
                return 0.0

        dfcutQ['priors_count'] = dfcutQ['priors_count'].apply(
            lambda x: quantizePrior(x))
        dfcutQ['length_of_stay'] = dfcutQ['length_of_stay'].apply(
            lambda x: quantizeLOS(x))
        dfcutQ['score_text'] = dfcutQ['score_text'].apply(
            lambda x: quantizeScore(x))
        dfcutQ['age_cat'] = dfcutQ['age_cat'].apply(lambda x: adjustAge(x))
        # Recode sex and race
        dfcutQ['sex'] = dfcutQ['sex'].replace({'Female': 1.0, 'Male': 0.0})
        dfcutQ['race'] = dfcutQ['race'].apply(lambda x: group_race(x))

        features = ['two_year_recid', 'race',
                    'age_cat', 'priors_count', 'c_charge_degree', 'score_text']

        # Pass vallue to df
        df = dfcutQ[features]

        return df

    XD_features = [
        'age_cat',
        'c_charge_degree',
        'priors_count',
        'race',
        'score_text']
    D_features = [
        'race'] if protected_attributes is None else protected_attributes
    Y_features = ['two_year_recid']
    X_features = list(set(XD_features) - set(D_features))
    categorical_features = [
        'age_cat',
        'priors_count',
        'c_charge_degree',
        'score_text']

    # privileged classes
    all_privileged_classes = {"sex": [1.0],
                              "race": [1.0]}

    # protected attribute maps
    all_protected_attribute_maps = {
        "sex": {
            0.0: 'Male', 1.0: 'Female'}, "race": {
            1.0: 'Caucasian', 0.0: 'Not Caucasian'}}

    return CompasDataset_test(
        label_name=Y_features[0],
        favorable_classes=[0],
        protected_attribute_names=D_features,
        privileged_classes=[all_privileged_classes[x] for x in D_features],
        instance_weights_name=None,
        categorical_features=categorical_features,
        features_to_keep=X_features + Y_features + D_features,
        na_values=[],
        metadata={'label_maps': [{1.0: 'Did recid.', 0.0: 'No recid.'}],
                  'protected_attribute_maps': [all_protected_attribute_maps[x]
                                               for x in D_features]},
        custom_preprocessing=custom_preprocessing)


privileged_groups = [{'race': 1}]
unprivileged_groups = [{'race': 0}]
dataset_orig_vt = load_preproc_data_compas(['race'])


def default_preprocessing(df):
    """Perform the same preprocessing as the original analysis:
    https://github.com/propublica/compas-analysis/blob/master/Compas%20Analysis.ipynb
    """
    return df[(df.days_b_screening_arrest <= 30)
              & (df.days_b_screening_arrest >= -30)
              & (df.is_recid != -1)
              & (df.c_charge_degree != 'O')
              & (df.score_text != 'N/A')]


class CompasDataset_train(StandardDataset):
    """ProPublica COMPAS Dataset.

    See :file:`aif360/data/raw/compas/README.md`.
    """

    def __init__(
            self,
            label_name='two_year_recid',
            favorable_classes=[0],
            protected_attribute_names=[
                'sex',
                'race'],
            privileged_classes=[
                ['Female'],
                ['Caucasian']],
            instance_weights_name=None,
            categorical_features=[
                'age_cat',
                'c_charge_degree',
                'c_charge_desc'],
            features_to_keep=[
                'sex',
                'age',
                'age_cat',
                'race',
                'juv_fel_count',
                'juv_misd_count',
                'juv_other_count',
                'priors_count',
                'c_charge_degree',
                'c_charge_desc',
                'two_year_recid',
                'length_of_stay'],
            features_to_drop=[],
            na_values=[],
            custom_preprocessing=default_preprocessing,
            metadata=default_mappings):
        """See :obj:`StandardDataset` for a description of the arguments.

        Note: The label value 0 in this case is considered favorable (no
        recidivism).

        Examples:
            In some cases, it may be useful to keep track of a mapping from
            `float -> str` for protected attributes and/or labels. If our use
            case differs from the default, we can modify the mapping stored in
            `metadata`:

            >>> label_map = {1.0: 'Did recid.', 0.0: 'No recid.'}
            >>> protected_attribute_maps = [{1.0: 'Male', 0.0: 'Female'}]
            >>> cd = CompasDataset(protected_attribute_names=['sex'],
            ... privileged_classes=[['Male']], metadata={'label_map': label_map,
            ... 'protected_attribute_maps': protected_attribute_maps})

            Now this information will stay attached to the dataset and can be
            used for more descriptive visualizations.
        """
        np.random.seed(1)

        def quantizePrior1(x):
            if x <= 0:
                return 0
            elif 1 <= x <= 3:
                return 1
            else:
                return 2

        def quantizeLOS(x):
            if x <= 7:
                return 0
            if 8 < x <= 93:
                return 1
            else:
                return 2

        def group_race(x):
            if x == "Caucasian":
                return 1.0
            else:
                return 0.0

        filepath = 'compas-train.csv'
        df = pd.read_csv(filepath, index_col='id', na_values=[])

        df['age_cat'] = df['age_cat'].replace('Greater than 45', 2)
        df['age_cat'] = df['age_cat'].replace('25 - 45', 1)
        df['age_cat'] = df['age_cat'].replace('Less than 25', 0)
        df['score_text'] = df['score_text'].replace('High', 1)
        df['score_text'] = df['score_text'].replace('Medium', 1)
        df['score_text'] = df['score_text'].replace('Low', 0)
        df['priors_count'] = df['priors_count'].apply(
            lambda x: quantizePrior1(x))
        df['length_of_stay'] = (pd.to_datetime(df['c_jail_out']) -
                                pd.to_datetime(df['c_jail_in'])).apply(
            lambda x: x.days)
        df['length_of_stay'] = df['length_of_stay'].apply(
            lambda x: quantizeLOS(x))
        df = df.loc[~df['race'].isin(
            ['Native American', 'Hispanic', 'Asian', 'Other']), :]
        df['c_charge_degree'] = df['c_charge_degree'].replace({'F': 0, 'M': 1})

        ix = df['days_b_screening_arrest'] <= 30
        ix = (df['days_b_screening_arrest'] >= -30) & ix
        ix = (df['is_recid'] != -1) & ix
        ix = (df['c_charge_degree'] != "O") & ix
        ix = (df['score_text'] != 'N/A') & ix
        df = df.loc[ix, :]

        df_neg = df.loc[df['two_year_recid'] == 1, :]
        df_neg_priv = df_neg.loc[(df_neg['two_year_recid'] == 1) & (
            df_neg['race'] == 'Caucasian'), :]
        df_neg_unpriv = df_neg.loc[(df_neg['two_year_recid'] == 1) & (
            df_neg['race'] == 'African-American'), :]

        _, df_neg_priv_test = train_test_split(
            df_neg_priv, test_size=460, random_state=10)
        _, df_neg_unpriv_test = train_test_split(
            df_neg_unpriv, test_size=990, random_state=10)
        df_neg_test = df_neg_priv_test.append(df_neg_unpriv_test)
        print('negative outcome, unpriv before fixing')
        print(len(df_neg_unpriv_test.index))

        print('negative outcome, priv before fixing')
        print(len(df_neg_priv_test.index))
        df_pos = df.loc[df['two_year_recid'] == 0, :]
        df_pos_priv = df_pos.loc[(df_pos['two_year_recid'] == 0) & (
            df_pos['race'] == 'Caucasian'), :]
        df_pos_unpriv = df_pos.loc[(df_pos['two_year_recid'] == 0) & (
            df_pos['race'] == 'African-American'), :]
        _, df_pos_priv_test = train_test_split(
            df_pos_priv, test_size=720, random_state=10)
        _, df_pos_unpriv_test = train_test_split(
            df_pos_unpriv, test_size=830, random_state=10)
        df_pos_test = df_pos_priv_test.append(df_pos_unpriv_test)
        print('positive outcome, unpriv before fixing')
        print(len(df_pos_unpriv_test.index))

        print('positive outcome, priv before fixing')
        print(len(df_pos_priv_test.index))
        df = df_neg_test.append(df_pos_test)

        df1 = df[['priors_count', 'c_charge_degree', 'race',
                  'age_cat', 'score_text', 'two_year_recid']]

        tot = []
        for index, row in df1.iterrows():
            result = ''
            for j in df1.columns:
                result = result + str(row[j])
            tot.append(result)
        df1['tmp_feature'] = tot
        df1['mis_prob'] = 0
        for i in df1['tmp_feature'].unique():
            if 'African' in i and i[-1] == '0':
                df1.loc[df1['tmp_feature'] == i, 'mis_prob'] = 0.8
            else:
                df1.loc[df1['tmp_feature'] == i, 'mis_prob'] = 0.05
        new_label = []
        np.random.seed(10)
        for i, j in zip(df1['mis_prob'], df1['priors_count']):
            if np.random.binomial(1, i, 1)[0] == 1:
                new_label.append(3)
            else:
                new_label.append(j)
        df['priors_count'] = new_label
        print('Total number of missing values')
        print(len(df.loc[df['priors_count'] == 3, :].index))
        print('Total number of observations')
        print(len(df.index))

        N = 3000
        df_result = pd.DataFrame()
        # statified sampling
        for i in df['two_year_recid'].unique():
            for j in df['race'].unique():
                orig_df = df.loc[(df['two_year_recid'] == i)
                                 & (df['race'] == j), :]
                orig_df_nomiss = df.loc[(df['two_year_recid'] == i) & (
                    df['race'] == j) & (df['priors_count'] == 3), :]
                real_count = len(orig_df.index)
                exp_count = int((len(df.loc[(df['two_year_recid'] == i), :].index) / len(
                    df.index)) * (len(df.loc[(df['race'] == j), :].index) / len(df.index)) * N)
                if real_count >= exp_count:
                    _, df_toapp = train_test_split(
                        orig_df, test_size=exp_count, random_state=10)
                else:
                    df_toapp = resample(
                        orig_df_nomiss,
                        replace=True,
                        n_samples=exp_count -
                        real_count,
                        random_state=10)
                    df_toapp = df_toapp.append(orig_df)
                if len(df_result.index) == 0:
                    df_result = df_toapp.copy()
                else:
                    df_result = df_result.append(df_toapp)
        df = df_result

        df['c_charge_degree'] = df['c_charge_degree'].replace({0: 'F', 1: 'M'})

        super(
            CompasDataset_train,
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


def load_preproc_data_compas(protected_attributes=None):
    def custom_preprocessing(df):
        """The custom pre-processing function is adapted from
            https://github.com/fair-preprocessing/nips2017/blob/master/compas/code/Generate_Compas_Data.ipynb
        """

        df = df[['age',
                 'c_charge_degree',
                 'race',
                 'age_cat',
                 'score_text',
                 'sex',
                 'priors_count',
                 'days_b_screening_arrest',
                 'decile_score',
                 'is_recid',
                 'two_year_recid',
                 'length_of_stay']]

        # Indices of data samples to keep
        ix = df['days_b_screening_arrest'] <= 30
        ix = (df['days_b_screening_arrest'] >= -30) & ix
        ix = (df['is_recid'] != -1) & ix
        ix = (df['c_charge_degree'] != "O") & ix
        ix = (df['score_text'] != 'N/A') & ix
        df = df.loc[ix, :]

        # Restrict races to African-American and Caucasian
        dfcut = df.loc[~df['race'].isin(
            ['Native American', 'Hispanic', 'Asian', 'Other']), :]

        # Restrict the features to use
        dfcutQ = dfcut[['sex',
                        'race',
                        'age_cat',
                        'c_charge_degree',
                        'score_text',
                        'priors_count',
                        'is_recid',
                        'two_year_recid',
                        'length_of_stay']].copy()

        # Quantize priors count between 0, 1-3, and >3
        def quantizePrior(x):
            if x == 0:
                return '0'
            elif x == 1:
                return '1 to 3'
            elif x == 2:
                return 'More than 3'
            else:
                return 'missing'
        # Quantize length of stay

        def quantizeLOS(x):
            if x == 0:
                return '<week'
            if x == 1:
                return '<3months'
            else:
                return '>3 months'

        # Quantize length of stay
        def adjustAge(x):
            if x == 1:
                return '25 to 45'
            elif x == 2:
                return 'Greater than 45'
            elif x == 0:
                return 'Less than 25'
        # Quantize score_text to MediumHigh

        def quantizeScore(x):
            if x == 1:
                return 'MediumHigh'
            else:
                return 'Low'

        def group_race(x):
            if x == "Caucasian":
                return 1.0
            else:
                return 0.0

        dfcutQ['priors_count'] = dfcutQ['priors_count'].apply(
            lambda x: quantizePrior(x))
        dfcutQ['length_of_stay'] = dfcutQ['length_of_stay'].apply(
            lambda x: quantizeLOS(x))
        dfcutQ['score_text'] = dfcutQ['score_text'].apply(
            lambda x: quantizeScore(x))
        dfcutQ['age_cat'] = dfcutQ['age_cat'].apply(lambda x: adjustAge(x))
        # Recode sex and race
        dfcutQ['sex'] = dfcutQ['sex'].replace({'Female': 1.0, 'Male': 0.0})
        dfcutQ['race'] = dfcutQ['race'].apply(lambda x: group_race(x))

        features = ['two_year_recid', 'race',
                    'age_cat', 'priors_count', 'c_charge_degree', 'score_text']

        # Pass vallue to df
        df = dfcutQ[features]

        return df

    XD_features = [
        'age_cat',
        'c_charge_degree',
        'priors_count',
        'race',
        'score_text']
    D_features = [
        'race'] if protected_attributes is None else protected_attributes
    Y_features = ['two_year_recid']
    X_features = list(set(XD_features) - set(D_features))
    categorical_features = [
        'age_cat',
        'priors_count',
        'c_charge_degree',
        'score_text']

    # privileged classes
    all_privileged_classes = {"sex": [1.0],
                              "race": [1.0]}

    # protected attribute maps
    all_protected_attribute_maps = {
        "sex": {
            0.0: 'Male', 1.0: 'Female'}, "race": {
            1.0: 'Caucasian', 0.0: 'Not Caucasian'}}

    return CompasDataset_train(
        label_name=Y_features[0],
        favorable_classes=[0],
        protected_attribute_names=D_features,
        privileged_classes=[all_privileged_classes[x] for x in D_features],
        instance_weights_name=None,
        categorical_features=categorical_features,
        features_to_keep=X_features + Y_features + D_features,
        na_values=[],
        metadata={'label_maps': [{1.0: 'Did recid.', 0.0: 'No recid.'}],
                  'protected_attribute_maps': [all_protected_attribute_maps[x]
                                               for x in D_features]},
        custom_preprocessing=custom_preprocessing)


def train():

    privileged_groups = [{'race': 1}]
    unprivileged_groups = [{'race': 0}]
    dataset_orig_train = load_preproc_data_compas(['race'])

    optim_options = {
        "distortion_fun": get_distortion_compas,
        "epsilon": 0.1,
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

    df_weight = dataset_orig_train.convert_to_dataframe()[0]
    df_weight['weight'] = 1
    df_weight['is_missing'] = 0
    df_weight['tmp'] = ''
    tmp_result = []
    for i, j in zip(df_weight['race'], df_weight['two_year_recid']):
        tmp_result.append(str(i) + str(j))
    df_weight['tmp'] = tmp_result

    df_weight.loc[df_weight['priors_count=missing'] == 1, 'is_missing'] = 1

    for i in df_weight['tmp'].unique():
        df_weight.loc[(df_weight['tmp'] == i) & (df_weight['is_missing'] == 0),
                      'weight'] = len(df_weight.loc[(df_weight['tmp'] == i),
                                                    :].index) / len(df_weight.loc[(df_weight['tmp'] == i) & (df_weight['is_missing'] == 0),
                                                                                  :].index)
        df_weight.loc[(df_weight['tmp'] == i) & (df_weight['is_missing'] == 1),
                      'weight'] = len(df_weight.loc[(df_weight['tmp'] == i) & (df_weight['is_missing'] == 0),
                                                    :].index) / len(df_weight.loc[(df_weight['tmp'] == i),
                                                                                  :].index)
    dataset_orig_train.instance_weights = np.array(df_weight['weight'])

    scale_transf = StandardScaler()
    X_train = scale_transf.fit_transform(dataset_transf_cat_train.features)
    y_train = dataset_transf_cat_train.labels.ravel()

    X_test = scale_transf.fit_transform(dataset_transf_cat_test.features)

    lmod = LogisticRegression()
    lmod.fit(
        X_train,
        y_train,
        sample_weight=dataset_orig_train.instance_weights)
    y_pred = lmod.predict(X_test)
    print('With fixing algorithms')
    print('Accuracy')
    print(accuracy_score(dataset_orig_vt.labels, y_pred))

    dataset_orig_vt_copy1 = dataset_orig_vt.copy()
    dataset_orig_vt_copy1.labels = y_pred

    metric_transf_train1 = BinaryLabelDatasetMetric(
        dataset_orig_vt_copy1,
        unprivileged_groups=unprivileged_groups,
        privileged_groups=privileged_groups)
    print('p-rule')
    print(min(metric_transf_train1.disparate_impact(),
              1 / metric_transf_train1.disparate_impact()))
    print('FPR for unpriv')
    orig_sens_att = dataset_orig_vt.protected_attributes.ravel()
    print(1 - TNR(dataset_orig_vt.labels.ravel()
                  [orig_sens_att == 0], y_pred[orig_sens_att == 0], 0))
    print("FNR for unpriv")
    print(1 - TPR(dataset_orig_vt.labels.ravel()
                  [orig_sens_att == 0], y_pred[orig_sens_att == 0], 0))

    print('FPR for priv')
    orig_sens_att = dataset_orig_vt.protected_attributes.ravel()
    print(1 - TNR(dataset_orig_vt.labels.ravel()
                  [orig_sens_att == 1], y_pred[orig_sens_att == 1], 0))
    print("FNR for priv")
    print(1 - TPR(dataset_orig_vt.labels.ravel()
                  [orig_sens_att == 1], y_pred[orig_sens_att == 1], 0))


if __name__ == '__main__':
    train()
