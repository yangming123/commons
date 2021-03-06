# ==================================================================================================
# Copyright 2011 Twitter, Inc.
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

java_library(name = 'io',
  provides = artifact(
    org = 'com.twitter.common',
    name = 'io',
    repo = pants('build-support/commons/ivy:public'),
  ),
  dependencies = [
    pants('3rdparty:commons-io'),
    pants('3rdparty:commons-lang'),
    pants('3rdparty:guava'),
    pants('src/java/com/twitter/common/base'),
  ],
  sources = [
    'Codec.java',
    'CompatibilityCodec.java',
    'FileUtils.java'
  ]
)

java_library(name = 'streamer',
  dependencies = [
    pants('3rdparty:guava'),
    pants('src/java/com/twitter/common/base'),
  ],
  sources = [ 'Streamer.java' ]
)

java_library(name = 'thrift',
  provides = artifact(
    org = 'com.twitter.common',
    name = 'io-thrift',
    repo = pants('build-support/commons/ivy:public'),
  ),
  dependencies = [
    pants('3rdparty:guava'),
    pants('3rdparty:thrift'),
    pants('src/java/com/twitter/common/base'),
    pants(':io'),
  ],
  sources = [ 'ThriftCodec.java' ]
)

java_library(name = 'json',
  provides = artifact(
    org = 'com.twitter.common',
    name = 'io-json',
    repo = pants('build-support/commons/ivy:public'),
  ),
  dependencies = [
    pants('3rdparty:gson'),
    pants('3rdparty:guava'),
    pants('src/java/com/twitter/common/base'),
    pants(':io'),
  ],
  sources = [ 'JsonCodec.java' ]
)
