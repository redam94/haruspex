"""This notebook contains helper classes and types for loading data from media datasets."""

# AUTOGENERATED! DO NOT EDIT! File to edit: ../../nbs/utils/00_data_loading.ipynb.

# %% ../../nbs/utils/00_data_loading.ipynb 3
from __future__ import annotations

import xarray as xr
import pandas as pd
import numpy as np
import numpyro as npy
import numpyro.distributions as dist
from numpyro.infer import MCMC, NUTS, Predictive

import jax
import jax.numpy as jnp
from jax import random as rnd

from typing import (
    Dict, Union, Literal, 
    Optional, Set, Tuple, 
    List, Callable, Generator)
import warnings
import os
import json
from pathlib import Path


# %% auto 0
__all__ = ['key_gen', 'build_datatree', 'ols_model', 'DataLoader']

# %% ../../nbs/utils/00_data_loading.ipynb 6
def key_gen(
  seed: int # seed for the random number generator
  ) -> Generator:
    key = rnd.PRNGKey(seed)
    while True:
      key, subkey = rnd.split(key, 2)
      yield subkey

# %% ../../nbs/utils/00_data_loading.ipynb 18
def build_datatree(
  mff: pd.DataFrame, # Dataframe in long format
  var_groups: Dict[str, List[str]], # Dictionary of variable groups
  group_common_coords: Dict[str, Union[Dict[str, List], List]], # Dictionary of common coords for each group or list of common dimensions
  ) -> xr.DataTree: # Returns a DataTree object
  "DataTree object"
  
  data_tree_dict = {}
  
  if isinstance(list(group_common_coords.values())[0], list):
      group_common_coords = {".": group_common_coords}

  data_tree_dict["."] = xr.Dataset(coords=group_common_coords['.'])
  for var_group in var_groups:
    if var_group=='.': continue
    data_tree_dict[f'/{var_group}'] = xr.Dataset(coords=group_common_coords.get(var_group, {}))
    for var in var_groups[var_group]:
      data_tree_dict[f'/{var_group}/{var}'] = xr.Dataset.from_dataframe(
        mff.query("VariableName == @var").set_index(
          ["Period", "Geography", "Product", "Campaign", "Outlet", "Creative"]
        )[['VariableValue']]
      )
  
  return xr.DataTree.from_dict(data_tree_dict)

# %% ../../nbs/utils/00_data_loading.ipynb 26
def ols_model(
    x: xr.DataArray, # DataArray of exogenous variables
    y: xr.DataArray, # DataArray of endogenous variable
    has_intercept: bool=True # whether to include an intercept in the model
    ) -> None:
    
    n, k = x.shape
    beta = npy.sample('beta', npy.distributions.Normal(np.zeros(k), 1))
    sigma = npy.sample('sigma', npy.distributions.Exponential(1))
    
    mean = jnp.dot(x.values, beta)
    if has_intercept:
        mean += npy.sample('intercept', npy.distributions.Normal(0, 1))
    npy.sample('y', npy.distributions.Normal(mean, sigma), obs=y.values if y is not None else None)

# %% ../../nbs/utils/00_data_loading.ipynb 32
class DataLoader:
    """Load data from a file or a directory of files, while keeping track of the metadata."""
    def __init__(
        self, 
        path: Union[str, Path], # path to the file or directory
        metadata_file_name: Optional[str] = None, # name of the metadata file
        custom_data_loader: Optional[Union[Callable, str]] = None # custom data loader function or name of module with custom data loader
        ) -> DataLoader:
        self.path = Path(path)
        self.metadata_file_name = metadata_file_name
        self.custom_data_loader = custom_data_loader
        self.data = self._load_data()
        
    def _load_data(self) -> Union[xr.Dataset, Dict[str, xr.Dataset]]:
        if self.path.is_file():
            return self._load_single_file(self.path)
        elif self.path.is_dir():
            return self._load_directory(self.path)
        else:
            raise FileNotFoundError(f"File or directory not found at {self.path}")
        
