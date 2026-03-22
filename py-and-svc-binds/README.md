# What does this module do?

This module has been created to talk with native Android services via the binder `/dev/binder`, in
their native language - Binder Parcelable Wire Protocol™ (so to speak - made up that name as I was writing this memo, but at least it is pretty accurate).

It also provides a set of function bindings to library `libbinder_ndk.so` (present on Android since ver. 10).
This .so lib is a stable gateway to interact with the services on the Android (which in fact work as a glorified Micro Services) without the need of tedious
knitting together the ioctl structures to be sent via BINDER_WRITE_READ. Or even worse - somehow using unstable C++ variant of that library (even I am not that crazy).

# But why bother?

A short and unsatisfactory answer: to turn on the flashlight, so Android is aware of that (sync with the widget in UI). Totally worth it (not really).
To read the full story behind this, see `README.md` next to the `hw-event-binder.py` script in the folder `hw-tinkering/hw-event-binder/`. As a matter of
fact that script uses the module from here, to achieve whatever it does.

# ~Elaboration~ Rant on the binds stability

The interface of the `libbinder_ndk.so` is stable, meaning: likely the functions and their symbols contained inside the lib, including whole framework (which indirectly counts in serialization of primitives) is here to stay.

**BEWARE MERE MORTAL**

On the contrary, though, the way of serialization for complex structures and numbers by which services' methods are accessed is free real estate, and it loves to change in between Android releases. At least it is consistent in between the services. For the most part, anyway. **FOR THE MOST PART.**

So be mindful when using those bindings. Especially when, the latest tag in this repo on which commit you're gonna use is based, differs from Android (LineageOS) version you are running.

## Here is real-live example of instability I happened to stumble upon (Mind, this is the edge of the edge cases, normally it is not so radical - the services are usually stable within the major release of Android. But it will give you the picture, I guess):
In the python lib provided here, there is a function verbosely called `is_torch_on_highly_unstable_unmantained()`, and aptly so, as what is happening there to retrieve system-wide flashlight status is pure wild west. 

*In fact, the inner working of that function proved to be so unstable, that I am now resorting to call `settings` binary directly, 
 as the method's `getContentProviderExternal()` number used in that function,
 changed a couple of times in span of the same release number of LineageOS after update. 
 This in itself wouldn't be THAT OF A PROBLEM, but to top that off, I am unable to get the proper method id from the online sources
 (likely LineageOS is doing some patchwork during the build), and the only reliable option (without rebuilding the LineageOS every single time after the update,
 which given the frequent update strategy of it and time it takes to build, is a major pain) was a guesswork AND IN CASE OF THAT INTERFACE GUESSING IS A REALLY BAD IDEA.
 See further reading to find out exactly why.*

But back to the example...  
The torch state is not directly exposed in any service's interface. Rather to ask about it you need to reach to the system settings for `flashlight_enabled` from secure realm.

And talking to the settings service is its own can of worms.  
**First off**, even though, there is a `settings` service running in the background:
```
# service list | grep settings                                                                                                                                   
145     lock_settings: [com.android.internal.widget.ILockSettings]
229     settings: []
```
It does not have any class associated (the name in between square brackets [] is empty). So in theory you could ask the
service manager (equivalent of glorified Yellow Pages from glorifieder Micro Services) for the reference to the service,
but you won't be able to create a proper binder with transaction to communicate with it. 

To do so you need to talk to `ActivityManager` and call `getContentProviderExternal()` method, so it'd gladly response to you with waaaaay too big parcel,
in which, somewhere, the proper binder for settings content provider is buried. In fact it is so big, I ditched
the idea of fully parsing it and created the heuristic seek algorithm for the binder returned in that parcel. Neat.

**To add on top of that**  
The binder you might or might not fish out from that ActivityManager's parcel (all hail heuristics), is not a reference to the `settings` service
or its interface. Oh no, that would be too simple.
Actually it is reference to interface called: `android.content.IContentProvider`.
And it would be fine and good, but it seems, that Android makers apparently historically couldn't decide on how referencing methods via binder should work, and to
access any given method in that particular binder, you don't reference the method by counting its ordinal number of appearance in class/aidl interface, as you usually do.

Rather, on the very bottom of the class's definition there are constants with the numbers associated with them. Starting from 1, **one**!  
Disrespect since the dawn of time... but at least this is consistent with modern .aidl approach. Even funnier it used to start from **TWO**, **TWO!!!** and it is not even .aidl or Matlab indexing madness, this is whole other level of evil.    
See [IContentProvider](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r4/core/java/android/content/IContentProvider.java#208) for your own if you don't believe me. Also, behold this historical version of [IActivityManager](https://android.googlesource.com/platform/frameworks/base/+/33f5ddd/core/java/android/app/IActivityManager.java#557) to see pure malice.  
Lovely, maybe at least that won't change, but don't get ahead of ourselves.

## Hear me out, here is THE REAL pitfall I foreshadowed
If everything I've described so far wouldn't be pityfally enough, look at the [IActivityManager](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r4/core/java/android/app/IActivityManager.aidl), there is our `getContentProviderExternal()` of interest, but not so far off there are: `killAllBackgroundProcesses()`, `enterSafeMode()` and other goodies.
The only things that are missing here are some methods of sort: `overheatBatteryAndCauseBlaze()` and `wipeAllDataWithoutConfirmation()`.

And mind you, those methods does not have stable enough numbers (and I'd really appreciate if they did, as in `IContentProvider`), so if anyone decide to add/remove some methods, you may happen to call whatever else from this class.  
Additionally, since getting the `flashlight_enabled` secure setting needs root access, now all that left for you to do is pray that the validation of the arguments passed via binder in those methods is robust. Or you can call other method unknowingly, when the interface discrepancy has happened. Fun.  
**Needless to say, last time between Android (LineageOS) version bump, my phone decided just to give up and rebooted when asked about torch state.**

## But when you think you have seen it all
Not only does this method risk a total system reboot if the IDs shift, it also creates *Immortal Processes™*.
that stay in your RAM till the end of the time, if you forget to tell the ActivityManager you're finished via `removeContentProviderExternal()`. 
Use it once, stay in memory forever. It's not a bug, it's a permanent residency.

Tell me about running untested code from the Internet. In my case I feel justified, though, at least I warned you!  

~Ehh, I should have just called `settings` binary for that. But hey! Now, it is not only overly complex, but also unreliable as well.~  
After last update, I regained my senses and in the end I am actually calling `settings` binary. Time well spent. See italic text at the very beginning 
of this chapter for more elaborate rationale for that.

# Serialization to Binder Parcelable Wire Protocol™

With the warning on the interfaces out of my chest, let's talk how one serializes/deserializes data in Android on the low level.

## libbinder_ndk.so abstraction
The library abstracts out a good chunk of otherwise pretty convoluted protocol. Most importantly it hides behind nifty functions retrieving the
instance of the binder associated with given service to talk with it, same goes for publishing your own service.
I won't be talking here about the latter one, though, maybe in the future. For now let's focus on talking to already existing services.

So we got the binder instance associated with the given service retrieved by `AServiceManager_getService`. What now?

Well, now we need to do two things, first associate a class with the service's binder by calling `AIBinder_associateClass`.
This later causes a write of a transaction's header implicitly, which is picked up by the service on transaction send, so it is aware what interface we are
gonna reference while talking with it.

When the association is done, we can now retrieve the pointer to the object by calling `AIBinder_prepareTransaction` on service binder,
to which, later on we can dump the serialized data itself.
The data dumped must follow the interface definition, usually specified by .aidl.

And here whole serialization madness begins.

There is a general rule of thumb in sending proper data to the service by merely looking on the .aidl interface, which I am going to describe further on.
With that being said, the whole thing that governs this parsing and dumping data is Java's IParcelable class, through its `createFromParcel` and `writeToParcel`
methods respectively. So if the common sense method does not work in your case, likely some custom shenanigans has been done there, and you must
refer to the original sources of the class, to see what is actually going on.

### Common sense rules to serialize interface arguments

- First and foremost, the data must be aligned to 4 bytes, the Binders to 8 bytes.
- The metadata of the types is almost non-existing in the on wire protocol, the interfaces governs the serialization. 
  Type confusion is likely if you mess something up. This way for example value 0x00000001 could be an integer of value one, or a boolean true.
- The `libbinder_ndk.so` provides functions to write primitives (bool, uint32, char, byte, float, double, int64, Binder, String). 
  And sometimes arrays of types (but this interface is whole other mess, as it usually requires an allocator as an argument. Realistically it is easier to simply
  manufacture the array by the bunch of int32 writes, than dealing with raw pointers in python). Those functions nicely handle the alignment.
- Strings are almost always represented as: `[length] + [UTF16 string] + [padding]`. In rare cases UTF-8 strings are needed. But the python lib here has function to handle those, namely:
  `_read_string8` and `_write_string8`.
- The array is usually just a `[length] + [data]`. It can be emulated by careful int32 writes, mind padding!.
- The more complex data, like structures are usually assembled out of primitives (int32, String, float, double etc.), once again: **mind per field padding!!**
- If the structure is not the first argument of the method, the deserializer often expects presence indication (single non-zero int32),
  telling that the structure is actually there. Sometimes writing simple 0x00000001 does not suffice and the size in bytes of structure is expected,
  and sometimes the presence plus the size is required (I am looking at you `AttributionSource`) in other cases version of structure may be expected there.
  In synopsis, whatever the maker's fantasy see to fit there, seems to be silently placed before the struct, but those honorable mentions are the most common patterns I encountered.
- Complex structures can be nulled/considered empty, by writing single int32 of zero (null, usually for structures), or negative one (empty usually for arrays/strings), depending on data
  type. And I've seen way too many picky deserializers where `nulled != empty` and vice versa.
- The callbacks on the side of the caller is handled via the Binders and `onTransaction` callback with proper class associated (mirror image of what is crafted to send data to service).
- To receive callbacks you need to spawn the thread pool, whose threads are delegated to handle them (so you need REAL thread safety there,
  not just python GIL type [GIL remark not true since python 3.14, best addition since switch..case ;)] ).

I won't be pasting a concrete examples here. Just take a look at the sources itself and confront it with the classes/interfaces from java/.aidl.
You have to do deep dive anyway on yourself if you want to add something on top of what this module provides. The above points are here to help you make sense of the code in the module.

### Okay but how do I target concrete method in the .aidl interface?

Well it is no mystery, the method number is usually just its ordinal number, while counting the methods from **one** in .aidl. 
So first method in the aidl is just referenced by number 1 in `AIBinder_transact` call, tenth is 10 etc.
There are exceptions for that (because of course there are) and it can get really messy. Just read the *Rant on binds stability* above for more details if you somehow missed that.

### Are there any limitations for `libbinder_ndk.so`?

Actually there are, and I hit two of them.

**Firstly**, you cannot call methods below FIRST_CALL_TRANSACTION (1) and above LAST_CALL_TRANSACTION (0x00ffffff -> 16777215) due to the pesky gatekeeper of `isUserCommand()` inside the function `AIBinder_transact`:  
https://android.googlesource.com/platform/frameworks/native/+/f99e2e3acf21451401afe11fca0dd69a36915d52/libs/binder/ndk/ibinder.cpp#632  
https://android.googlesource.com/platform/frameworks/native/+/f99e2e3acf21451401afe11fca0dd69a36915d52/libs/binder/ndk/ibinder_internal.h#32  
https://developer.android.com/reference/android/os/IBinder#FIRST_CALL_TRANSACTION  
https://developer.android.com/reference/android/os/IBinder#LAST_CALL_TRANSACTION  
And I am not sure where the check besides that place is (but surely there is one), since when I patched the library to skip that in the NDK lib (and I feel like they used inline function out of the spite here, just like in Spyro 3 on PS), the call didn't work either.
So no calling `SHELL_COMMAND_TRANSACTION` (0x5f434d44) system code for you pal.

**Secondly**, the exception string of error returned by the service tends to be stuck somewhere in between ioctl() and the library.
Basically, you are very lucky if you hear service complaining by calling function `_dump_parcel` from this module on the reply. 
Most often than not, you'll receive no info about your wrongdoing, being stuck just with counter-descriptive error code.  
Did it come from service or the library itself? None of your business apparently.

That being said and to not leave you on your own; to behold how to do the proper transaction debugging, please see section `Useful tools`, and `jtrace64` in particular.

# The least informative and exciting section. What is part of this module exactly?

The python module which is a sibling file to this README in most part is recreation of interfaces from **Android Binder NDK** (`libbinder_ndk.so`).  
It handles the manual serialization of data into `AParcel` objects and manages the lifecycle of `AIBinder` references via `ctypes`.

It also builds upon this, providing direct binding to various services on Android platform, which are used throughout tools in this repo.  
One caveat to keep in mind: functions of this module in many places are specialized for my use-cases and does not offer full parametrization, as they probably should.
Don't be surprised then, that `get_location` only cares about the fine location, as I never considered COARSE useful for me. Same goes for acquiring partial wake lock by default.  
You don't like it? Don't complain, patch it yourself.

### Breakdown of what is imported from the native library

| Original Name in Library                       | Python Internal Binding      | Purpose                                                             |
| :--------------------------------------------- | :--------------------------- | :------------------------------------------------------------------ |
| `AServiceManager_getService`                   | `_ndk_get_service`           | Retrieves a handle (AIBinder) to a registered system service.       |
| `AIBinder_prepareTransaction`                  | `_ndk_prepare_transaction`   | Allocates and prepares a Parcel object for an outgoing transaction. |
| `AIBinder_transact`                            | `_ndk_transact`              | Performs an IPC transaction between client and service.             |
| `AParcel_create`                               | `_ndk_parcel_create`         | Manually creates a new AParcel object.                              |
| `AParcel_delete`                               | `_ndk_parcel_delete`         | Destroys a Parcel object and frees its memory.                      |
| `AParcel_writeByte`                            | `_ndk_write_byte`            | Writes an 8-bit signed integer into a Parcel.                       |
| `AParcel_writeInt32`                           | `_ndk_write_int32`           | Writes a 32-bit signed integer into a Parcel.                       |
| `AParcel_writeInt64`                           | `_ndk_write_int64`           | Writes a 64-bit signed integer into a Parcel.                       |
| `AParcel_writeFloat`                           | `_ndk_write_float`           | Writes a 32-bit float into a Parcel.                                |
| `AParcel_writeString`                          | `_ndk_write_string`          | Takes an 8-bit string and writes UTF-16 one into a Parcel.          |
| `AParcel_writeStrongBinder`                    | `_ndk_write_strong_binder`   | Writes a strong reference to a binder object into a Parcel.         |
| `AParcel_writeParcelFileDescriptor`            | `_ndk_write_file_descriptor` | Writes a file descriptor into a Parcel.                             |
| `AParcel_readInt32`                            | `_ndk_read_int32`            | Reads a 32-bit signed integer from a Parcel.                        |
| `AParcel_readInt64`                            | `_ndk_read_int64`            | Reads a 64-bit signed integer from a Parcel.                        |
| `AParcel_readDouble`                           | `_ndk_read_double`           | Reads a 64-bit double from a Parcel.                                |
| `AParcel_readString`                           | `_ndk_read_string`           | Reads a string from a Parcel using a memory allocator callback.     |
| `AParcel_readStrongBinder`                     | `_ndk_read_strong_binder`    | Reads a strong reference to a binder object from a Parcel.          |
| `AParcel_getDataPosition`                      | `_ndk_get_pos`               | Returns the current read/write cursor position in the Parcel.       |
| `AParcel_setDataPosition`                      | `_ndk_set_pos`               | Sets the current read/write cursor position in the Parcel. Btw according to docs only positions returned by AParcel_getDataPosition are valid to use here.          |
| `AParcel_getDataSize`                          | `_ndk_get_data_size`         | Returns the total data size (in bytes) of the Parcel.               |
| `AParcel_marshal`                              | `_ndk_marshal`               | Copies raw Parcel data into a provided raw byte buffer.             |
| `AIBinder_Class_define`                        | `_ndk_class_define`          | Defines a new Binder class with lifecycle and transaction callbacks.|
| `AIBinder_new`                                 | `_ndk_aibinder_new`          | Creates a new instance of an AIBinder based on a defined class.     |
| `AIBinder_associateClass`                      | `_ndk_associate_class`       | Asserts that a binder belongs to a specific class/interface.        |
| `AIBinder_decStrong`                           | `_ndk_dec_strong`            | Decrements the strong reference count of a binder object.           |
| `AIBinder_incStrong`                           | `_ndk_inc_strong`            | Increments the strong reference count of a binder object.           |
| `ABinderProcess_setThreadPoolMaxThreadCount`   | `_ndk_set_max_threads`       | Configures the maximum number of binder threads.                    |
| `ABinderProcess_startThreadPool`               | `_ndk_start_thread_pool`     | Starts a threads pool to handle incoming binder transactions.       |
| `ABinderProcess_joinThreadPool`                | `_ndk_join_thread_pool`      | Makes current thread to wait for the binder threads in pool to end. |

### Auxiliary Utilities & Callbacks

* **`_android_string_allocator`**: A callback function passed to the NDK to allocate memory using `libc.malloc` when reading strings from a Parcel.
* **`_read_parcel_string`**: A high-level helper that reads a UTF-16 string from a Parcel, decodes it into a Python string, and frees the temporary C buffer.
* **`_read_string8`**: A legacy reader that manually extracts strings from a Parcel by processing data in 4-byte chunks. Expects UTF-8 like string in the parcel, instead default UTF-16.
* **`_write_string8`**: A legacy writer that serializes Python bytes into a Parcel in 4-byte chunks. Dumps UTF-8 like string to parcel, instead default UTF-16.
* **`_parcel_write_string_list`**: A utility to write a count-prefixed list of Python strings into a Parcel.
* **`_dump_parcel`**: A debugging tool that marshals Parcel data into a buffer and prints a formatted Hex/ASCII dump.
                      As the errors from services has hard time getting here, it is useful just for a quick preview of returned data. For debugging it is outclassed by `jtrace64`.
* **`_safe_dec_strong`**: A null-safe wrapper that decrements the reference count of a binder object to prevent memory leaks.
* **`_safe_parcel_delete`**: A null-safe wrapper that deletes and cleans up an `AParcel` object.

### Core Logic: Attribution & Binders

* **`_write_attribution_source`**: Manually serializes an `AttributionSourceState` (containing UID, PID, and package name) into a Parcel, which is required for security/identity verification in Android 12+ system services.
* **`_extract_binders`**: A heuristic scanner that iterates through a Parcel's memory to find and return any embedded `AIBinder` objects by checking for specific magic numbers (e.g., `0x73622A85`). 
                          Use when deserialization of whole object is not an option.

## Services bindings

### System Features: Torch, Power, & Display

* **`is_torch_on`**: Screws the rules and just calls `settings` binary to retrieve `flashlight_enabled` value to determine the current state of the torch
* **`is_torch_on_highly_unstable_unmantained`**: The name works here like a rattle for rattle snake. Do not use anywhere it if you are sane. I left it, just to keep an example of
  talking to the `ActivityManager`, `ContentProvider` and in the end retrieving settings. **I AM NOT GOING TO UPDATE THIS FUNCTION**, so it may do whatever to your system on the call.
  See ~Elaboration~ `Rant on the binds stability` chapter for details.
* **`set_torch_mode`**: Interacts with the `media.camera` service (`ICameraService`) to explicitly turn the device flashlight on or off for a specific camera ID.
* **`is_display_off`**: Uses the `power` service (`IPowerManager`) to check the `isInteractive` state, returning true if the display is not active.
* **`is_keyguard_active`**: Communicates with the `window` service (`IWindowManager`) to check if the Android keyguard (lock screen) is currently active.
* **`WakeLock` (Class)**: An RAII wrapper that manages an Android WakeLock; it ensures the lock is released and binder references are decremented when the object is deleted or exits a context.
* **`acquire_wake_lock`**: Creates a callback binder and requests a `PARTIAL_WAKE_LOCK` from the `power` service to prevent the CPU from sleeping.

### Location Services

* **`_write_location_request`**: A private helper that serializes a complex `LocationRequest` object into a Parcel, setting parameters like high accuracy, intervals, and provider type (GPS).
* **`AsyncLocationManager` (Class)**: Manages asynchronous communication with the `location` service; it defines a custom Binder class (`ILocationCallback`) to receive and parse location data (lat/lng, time, provider) from the system.
* **`get_location`**: A synchronous convenience function that uses `AsyncLocationManager` and a `threading.Event` to block execution until a location fix is acquired or a timeout is reached.

## Verifying if the services bindings work alright
The code guarded by `if __name__ == "__main__":` contains basic test for all interfacing with native Android services. Simply run that script as a python program and not imported library, to execute it.  
For complete test it has to be run twice; one time with root, other time without it, as some interfaces need special access. Also for full test, ACCESS_FINE_LOCATION permission is required for calling app.

## Future considerations

### Module split

To optimize for modularity, this code should be restructured into three logical layers: **Core FFI**, **Protocol/Marshalling**, and **Service API**.
For now it is as it is. But maybe, just maybe I'll refactor it in future (the always spawning thread pool is bugging me the most, as it is only needed for the services bindings and location service to be specific).

# Useful tools

This section documents what tools I was using during development of this module, their usage, tips and tricks and describes the transactions on the binder. So buckle up.

## Service

Usually built-in Android tool that allows you to list the services along with the classes associated with them.
The class name/interface can be later used while associating it with the binder retrieved with the ServiceManager. 
As described in `libbinder_ndk.so abstraction` section.

### Checking on services

To list all service simply call: `service list`, the result should look something like this:
```
# service list | head -n 10                                                                                                                                                                              
Found 292 services:
0       DockObserver: []
1       SurfaceFlinger: [android.ui.ISurfaceComposer]
2       SurfaceFlingerAIDL: [android.gui.ISurfaceComposer]
3       accessibility: [android.view.accessibility.IAccessibilityManager]
4       account: [android.accounts.IAccountManager]
5       activity: [android.app.IActivityManager]
6       activity_task: [android.app.IActivityTaskManager]
7       adb: [android.debug.IAdbManager]
8       adbroot_service: [android.adbroot.IADBRootService]
(...)
187     package: [android.content.pm.IPackageManager]
(...)
```

Besides that you can also check the status of the service by calling `service check <service name from list>`.
But this just underwhelmingly is telling you if the service was found or not. May be useful in script, though.

### Calling service's method

**To my utter surprise, you don't need root access for calling `service`. I mean it makes sense, but I was surprised nevertheless**

The `service` binary, besides providing the list of available services on the platform, it also allows to call the actual methods from the interfaces.
It is handy for quick tests. It becomes extremely tedious when dealing with structures (keeping track of the alignment, and fields themselves) and is no use when one needs to send
not-nulled binder, as it has no means to allocate such. I'd recommend it while calling methods which accept primitives only, handling more complex tasks is just way more convenient to be
done in python.

Simply call `service <service name, from list> <code> <type> <value> <type> <value>...`
Let's take for example `ApplicationInfo getApplicationInfo(String packageName, long flags, int userId);` (index `9`) from service `package` of interface 
[android.content.pm.IPackageManager](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r4/core/java/android/content/pm/IPackageManager.aidl#88).

It expects `String` as a first argument ( `service`'s `s16`), `long` as a second one (so `i64` in `service` nomenclature) and int as the last one (`i32` in service's call),
so the call goes as follows:
```bash
:# service call package 9 s16 "com.google.android.gms" i64 0  i32 0                                                                                                                                       
Result: Parcel(
0x00000000: 00000000 00000001 00000000 00000008 '................'
0x00000010: 672e6f63 7070412e 00000000 00000016 'co.g.App........'
0x00000020: 2e6d6f63 676f6f67 612e656c 6f72646e 'com.google.andro'
0x00000030: 672e6469 0000736d 7f15086a 00000001 'id.gms..j.......'
0x00000040: ffffffff 7f080312 00000000 ffffffff '................'
0x00000050: 00000000 ffffd8f0 00000000 00000016 '................'
0x00000060: 2e6d6f63 676f6f67 612e656c 6f72646e 'com.google.andro'
0x00000070: 672e6469 0000736d ffffffff 00000016 'id.gms..........'
0x00000080: 2e6d6f63 676f6f67 612e656c 6f72646e 'com.google.andro'
0x00000090: 672e6469 0000736d 00000008 672e6f63 'id.gms......co.g'
0x000000a0: 7070412e 00000000 00000000 a0cabec5 '.App............'
0x000000b0: a8089118 0000000d 00000000 00000000 '................'
(...)
```
**Pro tip** If you see `boolean` in the method's declaration it is just `i32` in disguise where `1` == `true`, and `0` == `false`.

For all the supported data types of `service` binary, the required padding is handled automatically. You can also craft some arbitrary data
by writing bunch of i32 (since no type metadata is stored in the parcel, therefore you can hack-in really crazy stuff here) but then maintaining the proper, 
usually 4-bytes alignment is on you.
You can also send nulled binder and file descriptors (and couple of other primitives), for details see `service` help string. 
I'll leave that as a exercise for the reader :)

To complete the docs in this section, **let's talk about returned data**, shall we?  
The first four bytes of response are the return code. All zeros indicates success. On error - if you are lucky - the service may decide to respond with some sensible error message,
if not, the first i32 (first four bytes), may tell you what kind of error you are dealing with. According to this:
https://android.googlesource.com/platform/frameworks/native/+/master/libs/binder/include/binder/Status.h#58
It is also recommended to observe logcat for commotion regarding your request.

But trust me it is way easier to just use `jtrace64` from the next chapter, to debug the traffic on the binder. It gives you a full picture
of data exchanged back and forth during the transaction, including the headers and more sensible errors indicators.

## jtrace64

**To my complete shock, you don't need root access for calling `jtrace64`. But it will allow you just to eavesdrop the traffic on the same privilege level.**

Let's set things straight here. Calling service's "simple" methods is well and good and in such case: return codes, logcat info and although rare, but highly appreciable error strings from 
services should suffice for such experiments. The example from the chapter above didn't require any specialized debug setup to preform the call, just a bit of practice.

### The travel matters, they say

With that being said, I hit a brick wall when I tried to do something more complex, like for example writing `AttributionSource` to the parcel.
I even looked into sources of `writeToParcel()` of that monstrosity, to see how it is actually serialized. Sadly, that bring no much help for actually composing the parcel sent on the wire.

At that point I said to myself: "there is no way in hell I am cracking it, without actually seeing what is going through transactions on binder".
And I've tried plenty of more-or-less dodgy solutions to do exactly that. Starting with `strace`, which although can give the insight into syscalls and can be instrumented to show
binders transaction only, unfortunately in the end it is unable to dump what is actually send in the data buffers.

Next, I tried to dump the data by combining the ioctl detection, with dumping `/proc/<pid>/maps` and `/proc/<pid>/mem`, of process in question (hell yeah, root access!).
But when I dug a bit deeper, the binder's transaction format turned out to be next level of a... let's say creative approach to structure data (reading: hell no, I am not parsing that).

Lastly, before the grant salvation and revelation, I tried Firda, all-having instrumentation toolkit. Which for my little surprise refused to work with LineageOS.
I don't even remember the exact reason, I believe something with aidl definition mismatch. And c'mon I am full grown adult, I am able to parse my hexdumps, alright. So I kept looking.

A while later, and probably after already having 3 crypto-miners on my device, along with five RATs running in background (heck yeah, root access!) I finally found, THE tool.
The tool as you might guess is called `jtrace64`.

### THE TOOL

The tool can be downloaded somewhere around here: https://newandroidbook.com/tools/jtrace.html
And this is exactly what I sought in my quest. A somewhat `strace` on steroids, tailored for Android and for the binder specifically, which is not fussy
about silly stuff such as lack of aidl definitions (Jonathan you are life and surely sanity saver. Thank you, heartfully!). 
At this point, .aidl to parcel translation and vice versa permanently etched in my mind and I don't need any preposterous aid with that (I think, I may need help, though XD).

### How do I use this?

Well best would be to see author's page for that, but I may give some pro tips here.

My basic usage is:
```
./jtrace64 -f -p <pid of process to attach>
```

The `-p` flag for process PID is required, consequentially it is impossible to do system-wide dump.
On the bright side, this shrinks logs by a lot (mind you, most of the traffic goes through binder on the Android).

Or other common usage (if only one instance of process of kind is running):
```
./jtrace64 -f -p $(pidof <process name>)
```

Here is another trick: If you are running external process, without ability to change its inner workings, you may achieve such "wait for attach" behavior simply by calling in shell:  
`sh -c 'read -p "Now attach with \'jtrace64 -f -p $$\', and press enter..."; exec <process to run>'`  
If that does not work (depends on system shell). You may use more crude version:  
`sh -c 'echo $$; read; exec <process to run>'`  
The exec makes the calling program (subshell), to be replaced by the specified one, so the pid stays the same. Any potential forks are captured by `-f` flag of `jtrace`.
The command separator `;` in the subshell is crucial, so no more subshells are spawned (which may sometimes happen on logical operator like `&&` or pipe `|`).

I think I don't need to add, it is best to run the debugged program in one instance of the shell, and the `jtrace` in the other.

### Example
Here is example, based on the `package` service call for `getApplicationInfo()` from the previous chapter. 

1. In one console I am running:
```bash
:# sh -c 'echo $$; read; exec service call package 9 s16 "com.google.android.gms" i64 0  i32 0'
24976
```
2. In the other I am now attaching to that subshell via jtrace, and I am redirecting the output to the file, as it may produce A LOT of data:
```bash
:# ./jtrace64 -f -v -p 24976 > out.log
```
3. Back to the first console, and I press enter there.

### Examining the response, or the treatise on binder's transactions

You will be greeted by the overwhelming amount of logs. But there are two chunks of the logs that are especially interesting for us
(but to be more general, search for BINDER_WRITE_READ, as those indicate actual transactions going on).

1. The call to the ServiceManager:
```
25033(service): ioctl (3 </dev/binder>, BINDER_WRITE_READ, [Write (68@0xb400007656f7a730)/Read (256@0xb400007656f77490)])
  Request (68/68 bytes @0xb400007656f7a730):
  0x00: BC_TRANSACTION on DSM (handle 0)    Code 4 Flags: FD (0x10) 
        (def)Method: android.os.IServiceManager::4
  -Buffer (@0xb400007526f6e250, 0x5c bytes):

    0xB400007526F6E250: 00 00 00 80  FF FF FF FF  54 53 59 53  1A 00 00 00  ........TSYS....
    0xB400007526F6E260: 61 00 6E 00  64 00 72 00  6F 00 69 00  64 00 2E 00  a.n.d.r.o.i.d...
    0xB400007526F6E270: 6F 00 73 00  2E 00 49 00  53 00 65 00  72 00 76 00  o.s...I.S.e.r.v.
    0xB400007526F6E280: 69 00 63 00  65 00 4D 00  61 00 6E 00  61 00 67 00  i.c.e.M.a.n.a.g.
    0xB400007526F6E290: 65 00 72 00  00 00 00 00  07 00 00 00  70 00 61 00  e.r.........p.a.
    0xB400007526F6E2A0: 63 00 6B 00  61 00 67 00  65 00 00 00                c.k.a.g.e...


  Reply (76/256 bytes @0xb400007656f77490) 
  0x00: BR_NOOP
  0x04: BR_TRANSACTION_COMPLETE
  0x08: BR_REPLY  to android.os.IServiceManager::?  Code 0  -Buffer (@0x7466e2e000, 0x34 bytes):

    0x7466E2E000: 00 00 00 00  01 00 00 00  00 00 00 00  01 00 00 00  ................
    0x7466E2E010: 24 00 00 00  85 2A 68 73  00 00 00 00  01 00 00 00  $....*hs........
    0x7466E2E020: 00 00 00 00  00 00 00 00  00 00 00 00  0C 00 00 00  ................
    0x7466E2E030: 00 00 00 00

    Object #0@0x7466e2e014 (0x14/0x34):handle Handle 1
```

This is us calling the Yellow Pages (`handle 0` - hardwired ServiceManager, `android.os.IServiceManager` - interface we are referring to, method no. `4`),
`(def)Method: android.os.IServiceManager::4`
for binder associated with the service in question `package`. 

And if we look into the sources, surely enough method number `4` is `Service checkService2(@utf8InCpp String name)`:
https://android.googlesource.com/platform//frameworks/native/+/refs/tags/android-16.0.0_r4/libs/binder/aidl/android/os/IServiceManager.aidl#99

Which actually is returning `Service` and not binder, but when I dug a little deeper, I stumbled upon following comment in Binder.cpp:
`Service implementations inherit from BBinder and IBinder, and this is frozen in prebuilts`
https://android.googlesource.com/platform//frameworks/native/+/refs/tags/android-16.0.0_r4/libs/binder/Binder.cpp#52

So the returned `Service` is serializable to flattened Binder when sending via `/dev/binder`, I guess.

The complete request looks like this:
```
    0xB400007526F6E250: 00 00 00 80  FF FF FF FF  54 53 59 53  1A 00 00 00  ........TSYS....
    0xB400007526F6E260: 61 00 6E 00  64 00 72 00  6F 00 69 00  64 00 2E 00  a.n.d.r.o.i.d...
    0xB400007526F6E270: 6F 00 73 00  2E 00 49 00  53 00 65 00  72 00 76 00  o.s...I.S.e.r.v.
    0xB400007526F6E280: 69 00 63 00  65 00 4D 00  61 00 6E 00  61 00 67 00  i.c.e.M.a.n.a.g.
    0xB400007526F6E290: 65 00 72 00  00 00 00 00  07 00 00 00  70 00 61 00  e.r.........p.a.
    0xB400007526F6E2A0: 63 00 6B 00  61 00 67 00  65 00 00 00                c.k.a.g.e...
```

In the request we have a header, which tells what class we are referencing, here `IServiceManager`:
```
    0xB400007526F6E250: 00 00 00 80  FF FF FF FF  54 53 59 53  1A 00 00 00  ........TSYS....
    0xB400007526F6E260: 61 00 6E 00  64 00 72 00  6F 00 69 00  64 00 2E 00  a.n.d.r.o.i.d...
    0xB400007526F6E270: 6F 00 73 00  2E 00 49 00  53 00 65 00  72 00 76 00  o.s...I.S.e.r.v.
    0xB400007526F6E280: 69 00 63 00  65 00 4D 00  61 00 6E 00  61 00 67 00  i.c.e.M.a.n.a.g.
    0xB400007526F6E290: 65 00 72 00  00 00 00 00  07 00 00 00  70 00 61 00  e.r.........
```

And for what service (to get a binder of `package`):
```
    0xB400007526F6E290: 65 00 72 00  00 00 00 00  07 00 00 00  70 00 61 00     .........p.a.
    0xB400007526F6E2A0: 63 00 6B 00  61 00 67 00  65 00 00 00                c.k.a.g.e...
```

So far so good. In response we get:
```
    0x7466E2E000: 00 00 00 00  01 00 00 00  00 00 00 00  01 00 00 00  ................
    0x7466E2E010: 24 00 00 00  85 2A 68 73  00 00 00 00  01 00 00 00  $....*hs........
    0x7466E2E020: 00 00 00 00  00 00 00 00  00 00 00 00  0C 00 00 00  ................
    0x7466E2E030: 00 00 00 00
```
And this asterisk and two letters after it should immediately catch your attention as this is most likely flattened binder reference to the target service.  
We also have info, that this binder is at handle `1` as per `Object #0@0x7466e2e014 (0x14/0x34):handle Handle 1`, but in fact the binders in the ioctl are not used
directly in package, but via their handle (which is reference to other place in memory. Btw. handle 0 is hard-coded for `ServiceManager`,
and it always is there. That's why we can always make a transaction to it, to get other service's reference).

This whole transaction is written and handled under the hood while calling `AServiceManager_getService()` from `libbinder_ndk.so`.

2. The other interesting thing is our actual call, this time to the destined service itself.
   (There is also call INTERFACE_TRANSACTION right before, which announces the start of transaction by writing Interface Descriptor [a safety handshake],
    but this one is boring in context of this memo).
   Here is the call with data, that we control:
```
25033(service): ioctl (3 </dev/binder>, BINDER_WRITE_READ, [Write (68@0xb400007656f7a730)/Read (256@0xb400007656f77490)])
  Request (68/68 bytes @0xb400007656f7a730):
  0x00: BC_TRANSACTION to handle 1  Code 9 Flags: FD (0x10) 
        (def)Method: android.content.pm.IPackageManager::9
  -Buffer (@0xb400007656f787b0, 0x98 bytes):

    0xB400007656F787B0: 00 00 00 80  FF FF FF FF  54 53 59 53  22 00 00 00  ........TSYS"...
    0xB400007656F787C0: 61 00 6E 00  64 00 72 00  6F 00 69 00  64 00 2E 00  a.n.d.r.o.i.d...
    0xB400007656F787D0: 63 00 6F 00  6E 00 74 00  65 00 6E 00  74 00 2E 00  c.o.n.t.e.n.t...
    0xB400007656F787E0: 70 00 6D 00  2E 00 49 00  50 00 61 00  63 00 6B 00  p.m...I.P.a.c.k.
    0xB400007656F787F0: 61 00 67 00  65 00 4D 00  61 00 6E 00  61 00 67 00  a.g.e.M.a.n.a.g.
    0xB400007656F78800: 65 00 72 00  00 00 00 00  16 00 00 00  63 00 6F 00  e.r.........c.o.
    0xB400007656F78810: 6D 00 2E 00  67 00 6F 00  6F 00 67 00  6C 00 65 00  m...g.o.o.g.l.e.
    0xB400007656F78820: 2E 00 61 00  6E 00 64 00  72 00 6F 00  69 00 64 00  ..a.n.d.r.o.i.d.
    0xB400007656F78830: 2E 00 67 00  6D 00 73 00  00 00 00 00  00 00 00 00  ..g.m.s.........
    0xB400007656F78840: 00 00 00 00  00 00 00 00                              ........
```

So we are now talking to the service at `handle 1` in our process, so from previous chat witch `ServiceManager` we know it is `package` service.
And by looking at the transaction header, we also know that we are referencing the class `android.content.pm.IPackageManager`:
```
    0xB400007656F787B0: 00 00 00 80  FF FF FF FF  54 53 59 53  22 00 00 00  ........TSYS"...
    0xB400007656F787C0: 61 00 6E 00  64 00 72 00  6F 00 69 00  64 00 2E 00  a.n.d.r.o.i.d...
    0xB400007656F787D0: 63 00 6F 00  6E 00 74 00  65 00 6E 00  74 00 2E 00  c.o.n.t.e.n.t...
    0xB400007656F787E0: 70 00 6D 00  2E 00 49 00  50 00 61 00  63 00 6B 00  p.m...I.P.a.c.k.
    0xB400007656F787F0: 61 00 67 00  65 00 4D 00  61 00 6E 00  61 00 67 00  a.g.e.M.a.n.a.g.
    0xB400007656F78800: 65 00 72 00  00 00 00 00  16 00 00 00  63 00 6F 00  e.r
```
The header is written implicitly, the class sent here is defined by function `AIBinder_associateClass`.

This is also reported by the `jtrace` itself in line: `(def)Method: android.content.pm.IPackageManager::9`, giving extra
info about the method number we are calling, here no. `9`.

So it all comes together.

After this, comes string with our package:
```
    0xB400007656F78800:                           16 00 00 00  63 00 6F 00          ....c.o.
    0xB400007656F78810: 6D 00 2E 00  67 00 6F 00  6F 00 67 00  6C 00 65 00  m...g.o.o.g.l.e.
    0xB400007656F78820: 2E 00 61 00  6E 00 64 00  72 00 6F 00  69 00 64 00  ..a.n.d.r.o.i.d.
    0xB400007656F78830: 2E 00 67 00  6D 00 73 00  00 00 00 00               ..g.m.s
```
Our `long` (zeored, so no much to show):
```
    0xB400007656F78830: 2E 00 67 00  6D 00 73 00  00 00 00 00  00 00 00 00             .....
    0xB400007656F78840: 00 00 00 00  00 00 00 00                              ....    
```
And int (also zeored, so even less to show, as it is 32 bit):
```
    0xB400007656F78840: 00 00 00 00  00 00 00 00                                  ....  
```

And that would be it on the usage of `jtrace` and interpreting the transaction data.
If you got here you can claim a reward of a picture of golden kettle (go find it yourself somewhere on the Internet). You're welcome!