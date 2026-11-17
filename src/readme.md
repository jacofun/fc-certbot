
> 注：当前项目为 Serverless Devs 应用，由于应用中会存在需要初始化才可运行的变量（例如应用部署地区、函数名等等），所以**不推荐**直接 Clone 本仓库到本地进行部署或直接复制 s.yaml 使用，**强烈推荐**通过 `s init ${模版名称}` 的方法或应用中心进行初始化，详情可参考[部署 & 体验](#部署--体验) 。

# fc-certbot 帮助文档
<p align="center" class="flex justify-center">
    <a href="https://www.serverless-devs.com" class="ml-1">
    <img src="http://editor.devsapp.cn/icon?package=fc-certbot&type=packageType">
  </a>
  <a href="http://www.devsapp.cn/details.html?name=fc-certbot" class="ml-1">
    <img src="http://editor.devsapp.cn/icon?package=fc-certbot&type=packageVersion">
  </a>
  <a href="http://www.devsapp.cn/details.html?name=fc-certbot" class="ml-1">
    <img src="http://editor.devsapp.cn/icon?package=fc-certbot&type=packageDownload">
  </a>
</p>

<description>

通过该模版，您可以将 Certbot 部署到函数计算中。此应用会使用 Certbot 生成证书。同时，配置了此应用生成的证书的 FC 自定义域名，将在证书到期之前自动进行续签，并更新自定义域名中配置的证书，从而保证证书的持续有效。

</description>

<codeUrl>



</codeUrl>
<preview>



</preview>


## 前期准备

使用该项目，您需要有开通以下服务并拥有对应权限：

<service>
</service>

<remark>



</remark>

<disclaimers>



</disclaimers>

## 部署 & 体验

<appcenter>
   
- :fire: 通过 [Serverless 应用中心](https://fcnext.console.aliyun.com/applications/create?template=fc-certbot) ，
  [![Deploy with Severless Devs](https://img.alicdn.com/imgextra/i1/O1CN01w5RFbX1v45s8TIXPz_!!6000000006118-55-tps-95-28.svg)](https://fcnext.console.aliyun.com/applications/create?template=fc-certbot) 该应用。
   
</appcenter>
<deploy>
    
- 通过 [Serverless Devs Cli](https://www.serverless-devs.com/serverless-devs/install) 进行部署：
  - [安装 Serverless Devs Cli 开发者工具](https://www.serverless-devs.com/serverless-devs/install) ，并进行[授权信息配置](https://docs.serverless-devs.com/fc/config) ；
  - 初始化项目：`s init fc-certbot -d fc-certbot`
  - 进入项目，并进行项目部署：`cd fc-certbot && s deploy -y`
   
</deploy>

## 案例介绍

<appdetail id="flushContent">

通过该模版，您可以将 Certbot 部署到函数计算中。此应用会使用 Certbot 生成证书。同时，配置了此应用生成的证书的 FC 自定义域名，将在证书到期之前自动进行续签，并更新自定义域名中配置的证书，从而保证证书的持续有效。

</appdetail>

## 使用文档

<usedetail id="flushContent">

1. 您的域名需要托管在“阿里云云解析 DNS”服务中。我们将使用 API 创建 TXT 解析记录，从而向 Let's Encrypt 证明域名属于您。
2. 如果您的域名在48小时内修改过DNS服务器，请您耐心等待或满48小时后再使用，因为解析记录变更生效一般需要等待24-48小时。这样 Let's Encrypt 的服务器才能正确解析到您的域名。
3. 部署成功后，请找到部署在杭州地域的 cert-generator 函数。并进入函数详情页面。
4. 点击“代码”页签中，“测试函数”旁边的下拉按钮，并点击“配置测试参数”。
  ![config](https://img.alicdn.com/imgextra/i3/O1CN018m9BmT1VBig71p3on_!!6000000002615-0-tps-672-554.jpg)
5. 输入您的要生成证书的域名的 JSON 内容，并点击“确定”。
   ```
      {
          "domainName": "abc.mydomain.com"
      }
    ```
    提示：支持通配符域名。
    ```
      {
          "domainName": "*.mydomain.com"
      }
    ```
   ![config](https://img.alicdn.com/imgextra/i3/O1CN01tbCzNf1Rm7hEBvpPZ_!!6000000002153-0-tps-1792-1612.jpg)
6. 点击“测试”来调用函数，并生成域名。
   ![config](https://img.alicdn.com/imgextra/i4/O1CN018es5JV1bB9t7GM8RG_!!6000000003426-0-tps-672-420.jpg)
7. 应用将使用 Certbot 通过 Let's Encrypt 生成证书，并将此证书上传到[数字证书管理服务](https://yundun.console.aliyun.com/?p=cas#/certExtend/upload/cn-hangzhou)。
8. 您可以在函数计算自定义域名创建或编辑页面中使用此证书。
   ![config](https://img.alicdn.com/imgextra/i2/O1CN010mXNqs1khyoTsmBoS_!!6000000004716-0-tps-1556-1198.jpg)
9. 每天凌晨，此应用会遍历您的函数计算自定义域名。在发现此应用生成的证书后，将自动检查证书的有效期，如果证书将在 7 天内过期，会更换证书，并更新函数计算自定义域名的证书配置。

</usedetail>

## 注意事项

<matters id="flushContent">
</matters>


<devgroup>


## 开发者社区

您如果有关于错误的反馈或者未来的期待，您可以在 [Serverless Devs repo Issues](https://github.com/serverless-devs/serverless-devs/issues) 中进行反馈和交流。如果您想要加入我们的讨论组或者了解 FC 组件的最新动态，您可以通过以下渠道进行：

<p align="center">  

| <img src="https://serverless-article-picture.oss-cn-hangzhou.aliyuncs.com/1635407298906_20211028074819117230.png" width="130px" > | <img src="https://serverless-article-picture.oss-cn-hangzhou.aliyuncs.com/1635407044136_20211028074404326599.png" width="130px" > | <img src="https://serverless-article-picture.oss-cn-hangzhou.aliyuncs.com/1635407252200_20211028074732517533.png" width="130px" > |
| --------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| <center>微信公众号：`serverless`</center>                                                                                         | <center>微信小助手：`xiaojiangwh`</center>                                                                                        | <center>钉钉交流群：`33947367`</center>                                                                                           |
</p>
</devgroup>


## 修复 OpenSSL.crypto.X509Req 初始化错误

`certbot==2.11.1` 与未锁定的间接依赖混装，会在导入旧证书代码时遇到已移除的 `OpenSSL.crypto.X509Req` 等 API。此版本将 Certbot/ACME 升级至 5.10.0，以 FC 的 Python 3.10 为解析目标，锁定包括 josepy、pyOpenSSL、cryptography 在内的完整依赖集合，支持 Python 3.10+。新依赖通过 cryptography 的 CSR API 工作，不要求 pyOpenSSL 恢复已删除的接口。

重新部署前必须清理旧的依赖目录，不能只修改 requirements.txt 后再次点击“测试函数”。在 Linux/Python 3.10 的 FC 构建环境内执行：

```sh
cd src/cert-generator
rm -rf python
python3.10 -m pip install --no-cache-dir -r requirements.txt -t python
python3.10 check_dependencies.py
```

上传时保持 `index.py`、`cas/`、`alidns/`、`scripts/`、`python/` 位于函数代码包根目录，入口仍为 `index.handler`。FC 环境变量 `PYTHONPATH` 使用 `/code/python:/code:/opt/python`，优先加载本次打包的依赖。若存在其他旧依赖层，也应避免其抢先覆盖打包版本。

模板的杭州申请函数部署前钩子会清理并重建共享 `cert-generator/python/` 目录、运行自检；手工上传或单独部署新加坡申请函数时，应先按上述命令构建共享代码目录，再部署。两个申请函数都应更新到同一份新代码和依赖包。

`check_dependencies.py` 验证锁定包的版本与来源、导入真实 FC 入口，并离线生成及验证一个 `.invalid` 域名的 RSA CSR。检查使用虚拟凭据并阻断网络，不会申请真实证书、更新 DNS 或访问云账户。GitHub 的 Check certificate dependencies 工作流在 Python 3.10 和 3.12 上执行同一检查。验证通过只说明依赖和本地 CSR 路径可用，实际签发仍需验证域名解析、角色权限与 ACME 连通性。

仓库现已使用 Deploy cert-generator to FC 工作流，main 更新会构建并更新指定的现有 FC 证书申请函数。部署完成后，再使用原 domainName 测试事件调用。

维护依赖时先修改 `src/cert-generator/requirements.in`，再使用 Python 3.10 解析约束生成锁定文件（例如 `uv pip compile src/cert-generator/requirements.in --python-version 3.10 --no-annotate --no-header -o src/cert-generator/requirements.txt`），并通过两种 Python 版本的 CI。不要直接用更高版本解释器的 pip freeze 覆盖 FC 3.10 锁定文件，否则会混入仅支持 Python 3.11+ 的间接依赖。


## GitHub 推送后自动部署现有证书申请函数

原模板的 `s registry publish` 流程已替换为 FC 代码部署，不需要 Serverless 模板仓库 Token。工作流读取本仓库 Settings → Secrets and variables → Actions 中的配置：

Repository secrets：

```json
{
  "ALIYUN_FC_ACCESS_KEY_ID": "部署账号 AccessKey ID",
  "ALIYUN_FC_ACCESS_KEY_SECRET": "部署账号 AccessKey Secret"
}
```

Repository variables：

```json
{
  "ALIYUN_FC_REGION": "cn-hangzhou",
  "ALIYUN_FC_FUNCTION_NAME": "实际的 cert-generator 函数名称"
}
```

地域以证书申请函数所在地域为准，不是它管理证书的业务函数地域。模板中的申请函数位于杭州或新加坡；部署账号需要目标函数的 `fc:GetFunction` 和 `fc:UpdateFunction` 权限。现有函数必须为 `python3.10`、`index.handler`，不匹配时在写入前停止。

推送 main 后，工作流会先验证部署配置，在 FC 官方 Python 3.10 构建镜像内重新安装锁定依赖、导入实际入口、生成离线 CSR，打包代码后通过官方 SDK 更新函数。PR 仅构建验证，不访问云账户。并发部署串行执行，过时的 main 提交不覆盖新版本。

部署保持函数角色、触发器、运行时、入口、超时、网络及其他环境变量，只将 PYTHONPATH 调整为 `/code/python:/code:/opt/python` 优先，并将原有额外路径追加保留。已有运行配置和私密值不会写入日志或部署产物。上传后读回代码 CRC64、运行时及配置进行校验，Actions Summary 中记录 sourceCommit 与代码校验值，ZIP 包与验证报告可在本次 Actions 的 Artifacts 下载。

工作流只更新配置所指向的一个现有申请函数，不创建应用中心模板中的其他函数，也不触发真实证书申请。若有其他地域的申请函数需要更新，请切换 Repository variables 到对应目标后，在 main 上执行 workflow_dispatch。实际申请使用原 domainName 测试事件，续期继续由已部署的定时管理函数负责。
