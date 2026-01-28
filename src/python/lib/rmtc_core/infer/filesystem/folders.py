# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project


from rmtc_core.io.filesystem.folders import FolderIO
from rmtc.artifacts import Repository
from rmtc.infer import Inferer
from rmtc.system import URI, Context
from rmtc.io import IO


class FolderInferer(Inferer):
    """
    Batch inference processor for entire folders of input files.

    The FolderInferer class extends the base Inferer to provide batch processing
    capabilities for folders containing multiple input files. It automatically
    discovers compatible files in the input directory, processes them through
    the specified model, and saves results to an output directory with
    corresponding filenames.

    This inferer is particularly useful for batch processing scenarios where
    you need to apply a model to many files at once, such as image enhancement,
    style transfer, or other file-to-file transformations. It handles file
    discovery, asset creation, inference execution, and result persistence
    automatically.
    """

    def __init__(
        self,
        model=None,
        weights=None,
        input_uri=URI(),
        output_uri=URI(),
        input_io=None,
        output_io=None,
        context=Context.GPU,
        postprocess=None,
    ):
        # TODO : input_io & output_io must match signature of model
        """Initialize FolderInferer with model, paths, and file handlers."""
        super(FolderInferer, self).__init__(
            model=model,
            weights=weights,
            context=context,
            postprocess=postprocess,
        )
        self.add_property("input_uri", URI, input_uri)
        self.add_property("input_io", IO, input_io)
        self.add_property("output_uri", URI, output_uri)
        self.add_property("output_io", IO, output_io)

    def __call__(self):
        """Execute batch inference on all compatible files in the input folder."""

        # create source folder dataset
        # NOTE : that model.input_type is a Type object
        # if we pass a Type directly to a property constructor,
        # you end up wrapping your class with a Type which then fails
        # on serialisation
        inputs = Repository(
            uri=self.input_uri,
            io=FolderIO(
                asset_type=self.model.input_type,
                asset_io=self.input_io,
            ),
        )

        # create output dataset dataset
        outputs = Repository(
            uri=self.output_uri,
            io=FolderIO(
                asset_type=self.model.output_type,
                asset_io=self.output_io,
            ),
        )

        # run
        inference = self.run(inputs=inputs, outputs=outputs)

        # return
        return inference
