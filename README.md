# Gitex Demo - Charmed Spark

This repository contains the material of the Demo used for Gitex 2023 for Charmed Spark

## Prerequisite

* Ubuntu 22.04
* Kaggle API Key to download the data
* *(Optional)* `yq` and `docker` installed

## Setup

To carry out this demo, we will need a few components that needs to be installed.

### MicroK8s

```shell
sudo snap install microk8s --channel 1.27-strict/stable --classic
sudo microk8s enable hostpath-storage dns rbac storage
sudo snap alias microk8s.kubectl kubectl 
microk8s config > ~/.kube/config
```

MicroK8s will be used for deploying Spark workload locally.

### S3 Object Storage

If there is connection to an existing central Object storage, you can use that one. Otherwise, 
you can use MicroK8s built-in adds of MinIO for storing data of SparkJobs. To enable MinIO

```shell
sudo microk8s enable minio

IPADDR=$(ip -4 -j route get 2.2.2.2 | jq -r '.[] | .prefsrc')
microk8s enable metallb:$IPADDR-$IPADDR
```

To make sure that MinIO is up and running, you can run the script 

```shell
./bin/check_minio.sh
```

That should output that the service is up and running and provide you with the endpoints and the
credentials (access key and access secret).

You can also access to the MinIO Web UI by fetching the IP of the service related to the UI:

```shell
MINIO_UI_IP=$(kubectl get svc microk8s-console -n minio-operator -o yaml | yq .spec.clusterIP)
```

And navigate using your browser to `http://$MINIO_UI_IP:9090`.

We also suggest to create some environment variables for storing S3 credentials and endpoints, such that
you can use the scripts below as-is

```shell
export AWS_S3_ENDPOINT=<s3-endpoint>
export AWS_S3_BUCKET=<bucket-name> # This can be up to you, suggested charmed-spark-gitex-demo
export AWS_ACCESS_KEY=<your-access-key>
export AWS_SECRET_KEY=<your-secret-key>
```

### Juju CLI 

```shell
sudo snap install juju --channel 3.1/stable
```

The Juju CLI will be used for interacting with the Juju controller
for managing services via charmed operators.

<!-- 
###### `yq` 

```shell
sudo snap install yq
```

`yq` will be used to parse and patch YAML files.

###### `docker` 

```shell
sudo snap install docker
sudo addgroup --system docker
sudo adduser $USER docker
sudo snap disable docker
sudo snap enable docker
```

`yq` will be used to parse and patch YAML files.

-->

### `spark-client`

```shell
sudo snap install spark-client --channel 3.4/edge
```

The `spark-client` Snap provides a number of utilities to manage Spark service accounts as well 
starting Spark job on a K8s cluster. 

### Resources

Once all the components are installed, we then need to set up a S3 bucket and copy the relevant 
data from this repository in, e.g.`data` and `script`, that will be used in this demo.

The code below uses some python scripts for doing some of the task required in the setup. We 
suggest you to create a Python virtualenv and install the relevant packages with 

```shell
pip install -r requirements.txt
```

First, generate the data to be used in the Demo. Make sure that you have your Kaggle credentials
setup in the `~/.kaggle/kaggle.json` file. Then run the following script

```shell
python3 scripts/dataset_generation.py
```

This will download the dataset from Kaggle and patch it accordingly for the sake of the Case in 
the demo.

Next upload the generated file in the S3 bucket. 
In order to do so, you can use the Python scripts bundled in this repository for creating and 
setting up (e.g. copying the files needed for the demo) the S3 bucket

```shell
python3 scripts/spark_bucket.py \
  --action create setup \
  --access-key $AWS_ACCESS_KEY \
  --secret-key $AWS_SECRET_KEY \
  --endpoint $AWS_S3_ENDPOINT \
  --bucket $AWS_S3_BUCKET 
```

#### Setup Monitoring tools

You need to bootstrap a Juju controller responsible for managing your services

```shell
juju bootstrap microk8s micro
```

##### Deploy the charms

First, add a new model/namespace where to deploy the History Server related charms

```shell
juju add-model spark
```

You can now deploy all the charms required by the Monitoring stack, using the provided bundle 
(but replacing the environment variable)

```shell
juju deploy --trust \
 <( yq e '.applications.s3-integrator.options.bucket=strenv(AWS_S3_BUCKET) | .applications.s3-integrator.options.endpoint=strenv(AWS_S3_ENDPOINT)' ./confs/bundle.yaml )
```

##### Setup the charms 

Once the charms are deployed, you need to perform some configurations to setup the history-server
charm to correctly read the data from the S3 logs.

###### S3 Integrator 

the `s3-integrator` needs to be correctly configured by providing the S3 credentials, e.g. 

```shell
juju run s3-integrator/leader sync-s3-credentials \
  access-key=$AWS_ACCESS_KEY secret-key=$AWS_SECRET_KEY
```

##### Integrate the charms

At this point, the `spark-history-server-k8s` can be related to the `s3-integrator` to provide
the S3 credentials to the Spark History server to be able to read the logs from the object storage. 

```shell
juju relate spark-history-server-k8s s3-integrator
```

<!---
##### Import Spark Dashboards (optional)

If you want to have some simple Spark dashboard already available to you in Grafana, configure 
this using the `cos-configuration-k8s` charm. 

> Note that you should have read access to the Github repository below for this  to work

```shell
juju deploy cos-configuration-k8s \
  --config git_repo=https://github.com/canonical/charmed-spark-rock \
  --config git_branch=dashboard \
  --config git_depth=1 \
  --config grafana_dashboards_path=dashboards/prod/grafana/
```

Once this is deployed, you can relate to grafana in order to provide the dashboard across the 
relation

```shell
juju relate cos-configuration-k8s grafana
```
-->

##### Fetch your endpoints!

Once the charms settle down into `active/idle` states, you can then fetch the external Spark 
History Server URL using `traefik` via the action

```shell
juju run traefik/leader show-proxied-endpoints
```

As you can see from the output of the action, you will now have two tools to perform monitoring:
1. Spark History Server, that is a UI that most Spark users are accustomed to, to analyze their
 jobs, at a more business level (e.g. jobs separated by the different steps and so on). Spark 
 History server does not support authentication yet. 
2. Grafana Dashboards, that is more oriented to cluster administrators, allowing to set up alerts
 and dashboarding based on resource utilization. In order to retrive the credentials for logging
 into the Grafana dashboard, use the following action:
```shell
juju run grafana/leader get-admin-password
```

#### Setup K8s to run Spark Jobs

You can now create the Spark service account on the K8s cluster that will be used to run the 
Spark workloads. The services will be created via the `spark-client.service-account-registry`
as `spark-client` will provide enhanced features to run your Spark jobs seamlessly integrated 
with the other parts of the Charmed Spark solution. 

For instance, `spark-client` allows you to bind your service account a hierarchical set of 
configurations that will be used when submitting Spark jobs. For instance, in this demo we will 
use S3 bucket to fetch and store data. Spark settings are specified in a 
[configuration file](./confs/s3.conf) and can be fed into the service account creation command,
 also handling the parsing of environment variables specified in the configuration file, such as:

* S3 Bucket credentials provided above, `AWS_*` env variables
* Endpoint of Prometheus pushgateway for pushing the driver and executor metrics:

```shell
export PROMETHEUS_GATEWAY=$(juju status --format=yaml | yq ".applications.prometheus-pushgateway-k8s.address") 
export PROMETHEUS_PORT=9091
```

We can now create the Spark service account that will be used to run workloads:

```shell
spark-client.service-account-registry create \
  --username spark --namespace spark \
  --properties-file ./confs/spark-service-account.conf
```

You can find more information about the hierarchical set of configurations 
[here](https://discourse.charmhub.io/t/spark-client-snap-explanation-hierarchical-configuration-handling/8956) 
and how to manage Spark service account via `spark-client` 
[here](https://discourse.charmhub.io/t/spark-client-snap-tutorial-manage-spark-service-accounts/8952)

That's it! You are now ready to use Spark!

#### Setup Jupyter Environment

It is always very convenient when you are either exploring some data or doing some first development
to use Jupyter notebook, assisted with a user-friendly and interactive environment where you can 
mix python (together with plots) and markdown code.

To start a Jupyter notebook server that provides a binding to Spark already integrated in 
your notebooks, you can run the Charmed Spark OCI image

```shell
docker run --name charmed-spark --rm \
  -v $HOME/.kube/config:/var/lib/spark/.kube/config \
  -v $(pwd):/var/lib/spark/notebook/repo \
  -p 8080:8888 \
  ghcr.io/canonical/charmed-spark:3.4-22.04_edge \
  \; start jupyter 
```

It is important for the image to have access to the Kubeconfig file (in order to fetch the 
Spark configuration via the `spark-client` CLI) as well as the local notebooks directory to access 
to the notebook already provided. 

> :warning: If you want to read/write to the notebook directory (e.g. for opening/saving notebooks)
> please make sure you set the permission of the folder correctly. Note that the jupyter process
> will be running in a docker container with a user named *_daemon_*.  

When the image is up and running, you can navigate with your browser to

```shell
http://localhost:8080
```

Open the notebook provided for starting the Exercise .
As you start a new notebook, you will already have a `SparkContext` and a `SparkSession` object 
defined by two variables, `sc` and `spark` respectively,

```python
> sc
SparkContext

Spark UI

Version           v3.4.1
Master            k8s://https://192.168.1.4:16443
AppName           PySparkShell
```

In fact, the notebook (running locally on Docker) acts as driver, and it spawns executor pods on 
Kubernetes. This can be confirmed by running

```shell
kubectl get pod -n spark
```

which should output something like

```shell
NAME                                                        READY   STATUS      RESTARTS   AGE
pysparkshell-79b4df8ad74ab7da-exec-1                        1/1     Running     0          5m31s
pysparkshell-79b4df8ad74ab7da-exec-2                        1/1     Running     0          5m29s
```


### Cleanup

First destroy the Juju model and controller

```shell
juju destroy-controller --force --no-wait \
  --destroy-all-models \
  --destroy-storage micro
```

Finally, you can also remove the S3-bucket that was used during the demo via the provided Python
script

```shell
python3 scripts/spark_bucket.py \
  --action delete \
  --access-key $AWS_ACCESS_KEY \
  --secret-key $AWS_SECRET_KEY \
  --endpoint $AWS_S3_ENDPOINT \
  --bucket $AWS_S3_BUCKET 
```



