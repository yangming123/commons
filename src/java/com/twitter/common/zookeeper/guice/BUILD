# ==================================================================================================
# Copyright 2012 Twitter, Inc.
# --------------------------------------------------------------------------------------------------
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this work except in compliance with the License.
# You may obtain a copy of the License in the LICENSE file, or at:
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==================================================================================================

java_library(name = 'guice',
  provides = artifact(
    org = 'com.twitter.common.zookeeper',
    name = 'guice',
    repo = pants('build-support/commons/ivy:public'),
  ),
  dependencies = [
    pants('3rdparty:guava'),
    pants('3rdparty:guice'),
    pants('src/java/com/twitter/common/application/modules:lifecycle'),
    pants('src/java/com/twitter/common/application:action'),
    pants('src/java/com/twitter/common/args'),
    pants('src/java/com/twitter/common/base'),
    pants('src/java/com/twitter/common/zookeeper:client'),
    pants('src/java/com/twitter/common/zookeeper:group'),
    pants('src/java/com/twitter/common/zookeeper:server-set'),
    pants('src/thrift/com/twitter/thrift'),
  ],
  sources = globs('*.java'),
)
