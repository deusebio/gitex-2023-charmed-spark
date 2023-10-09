#!/bin/bash

attempt=1
while [ $attempt -le 10 ]
do
  # echo "s3 params setup attempt=$attempt"
  if [ -z "$access_key" ]; then
    access_key=$(sudo microk8s.kubectl get secret -n minio-operator microk8s-user-1 -o jsonpath='{.data.CONSOLE_ACCESS_KEY}' | base64 -d)
  fi
  if [ -z "$secret_key" ]; then
    secret_key=$(sudo microk8s.kubectl get secret -n minio-operator microk8s-user-1 -o jsonpath='{.data.CONSOLE_SECRET_KEY}' | base64 -d)
  fi
  if [ -z "$endpoint_ip" ]; then
    endpoint_ip=$(sudo microk8s.kubectl get services -n minio-operator | grep minio | awk '{ print $3 }')
    endpoint="http://$endpoint_ip:80"
  fi

  if [ -z "$access_key" ] || [ -z "$secret_key" ] || [ -z "$endpoint_ip" ]
  then
        if [ $attempt -ge 10 ];then
            echo "ERROR: s3 params setup failure, aborting." >&2
            exit 1
        fi

        echo "[$attempt] s3 params are still missing (see above), retrying in 3 secs..."
        sleep 3
        let "attempt+=1"
  else
        break
  fi
done

echo "S3 Bucket up and running!"
echo " "
echo "Endpoint: ${endpoint}"
echo "Access Key: ${access_key}"
echo "Access Secret: ${secret_key}"