define build_echo_python_function
	python -m pip install -r src/aws_runtime/requirements.txt -t $(ARTIFACTS_DIR)
	cp -r src $(ARTIFACTS_DIR)/src
	cp -r scripts $(ARTIFACTS_DIR)/scripts
	cp -r schemas $(ARTIFACTS_DIR)/schemas
endef

build-EchoRuntimeFunction:
	$(build_echo_python_function)

build-EchoSchemaMigrationFunction:
	$(build_echo_python_function)

build-EchoEnterpriseBootstrapFunction:
	$(build_echo_python_function)

build-EchoObservationImportFunction:
	$(build_echo_python_function)
